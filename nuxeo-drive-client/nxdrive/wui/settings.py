'''
Created on 27 janv. 2015

@author: Remi Cattiau
'''
from PyQt4 import QtCore
from nxdrive.logging_config import get_logger
log = get_logger(__name__)

from nxdrive.wui.dialog import WebDialog, WebDriveApi
from nxdrive.wui.authentication import WebAuthenticationApi
from nxdrive.wui.authentication import WebAuthenticationDialog
from nxdrive.manager import ProxySettings, FolderAlreadyUsed
from nxdrive.client.base_automation_client import Unauthorized
from nxdrive.wui.translator import Translator
from nxdrive.utils import DEVICE_DESCRIPTIONS
from nxdrive.utils import TOKEN_PERMISSION
import sys
import urllib2
import httplib
import urlparse
from urllib import urlencode

DRIVE_STARTUP_PAGE = 'drive_login.jsp'


class StartupPageConnectionError(Exception):
    pass


class WebSettingsApi(WebDriveApi):

    def __init__(self, application, dlg=None):
        super(WebSettingsApi, self).__init__(application, dlg)
        # Attributes for the web authentication feedback
        self._new_local_folder = ""
        self._account_creation_error = ""
        self._token_update_error = ""

    @QtCore.pyqtSlot(result=str)
    def get_default_section(self):
        try:
            return self._dialog._section
        except Exception as e:
            log.exception(e)
            return ""

    @QtCore.pyqtSlot(result=str)
    def get_default_nuxeo_drive_folder(self):
        try:
            folder = self._manager.get_default_nuxeo_drive_folder()
            return folder
        except Exception as e:
            log.exception(e)
            return ""

    @QtCore.pyqtSlot(str, result=str)
    def unbind_server(self, uid):
        try:
            self._manager.unbind_engine(str(uid))
        except Exception as e:
            log.exception(e)
        return ""

    @QtCore.pyqtSlot(str, result=str)
    def filters_dialog(self, uid):
        try:
            engine = self._get_engine(uid)
            if engine is None:
                return "ERROR"
            self._application.show_filters(engine)
        except Exception as e:
            log.exception(e)
        return ""

    def _bind_server(self, local_folder, url, username, password, name, start_engine=True):
        local_folder = str(local_folder.toUtf8()).decode('utf-8')
        url = str(url)
        username = str(username)
        password = str(password)
        name = unicode(name)
        if name == '':
            name = None
        self._manager.bind_server(local_folder, url, username, password, name=name, start_engine=start_engine)
        return ""

    @QtCore.pyqtSlot(str, str, str, str, str, result=str)
    def bind_server(self, local_folder, url, username, password, name):
        try:
            # Allow to override for other exception handling
            return self._bind_server(local_folder, url, username, password, name)
        except Unauthorized:
            return "UNAUTHORIZED"
        except FolderAlreadyUsed:
            return "FOLDER_USED"
        except urllib2.URLError as e:
            if e.errno == 61:
                return "CONNECTION_REFUSED"
            return "CONNECTION_ERROR"
        except urllib2.HTTPError as e:
            return "CONNECTION_ERROR"
        except Exception as e:
            log.exception(e)
            # Map error here
            return "CONNECTION_UNKNOWN"

    def create_account(self, local_folder, url, username, token, name, start_engine=True):
        self._manager.bind_server(local_folder, url, username, None, token=token, name=name, start_engine=start_engine)

    @QtCore.pyqtSlot(str, str, str, result=str)
    def web_authentication(self, local_folder, server_url, engine_name):
        try:
            # Handle local folder
            local_folder = str(local_folder.toUtf8()).decode('utf-8')
            self._check_local_folder(local_folder)

            # Handle server URL
            server_url = str(server_url)
            if not server_url.endswith('/'):
                server_url += '/'

            # Connect to startup page
            status = self._connect_startup_page(server_url)
            if status < 400:
                # Page exists, let's open authentication dialog
                engine_name = unicode(engine_name)
                if engine_name == '':
                    engine_name = None
                callback_params = {
                    'local_folder': local_folder,
                    'server_url': server_url,
                    'engine_name': engine_name,
                }
                url = self._get_authentication_url(server_url)
                log.debug('Web authentication is available on server %s, opening login window with URL %s',
                          server_url, url)
                self._open_authentication_dialog(url, callback_params)
                return "true"
            else:
                # Startup page is not available
                log.debug('Web authentication not available on server %s, falling back on basic authentication',
                          server_url)
                return "false"
        except FolderAlreadyUsed:
            return 'FOLDER_USED'
        except StartupPageConnectionError:
            return 'CONNECTION_ERROR'
        except:
            log.exception('Unexpected error while trying to open web authentication window')
            return 'CONNECTION_UNKNOWN'

    def _check_local_folder(self, local_folder):
        if not self._manager.check_local_folder_available(local_folder):
            raise FolderAlreadyUsed()

    def _connect_startup_page(self, server_url):
        conn = None
        try:
            parsed_url = urlparse.urlparse(server_url)
            scheme = parsed_url.scheme
            hostname = parsed_url.hostname
            port = parsed_url.port
            path = parsed_url.path
            path += DRIVE_STARTUP_PAGE
            if scheme == 'https':
                conn = httplib.HTTPSConnection(hostname, port)
            else:
                conn = httplib.HTTPConnection(hostname, port)
            conn.request('HEAD', path)
            status = conn.getresponse().status
            log.debug('Status code for %s = %d', server_url + DRIVE_STARTUP_PAGE, status)
            return status
        except:
            log.exception('Error while trying to connect to Nuxeo Drive startup page with URL %s', server_url)
            raise StartupPageConnectionError()
        finally:
            if conn is not None:
                conn.close()

    def update_token(self, engine, token):
        engine.update_token(token)

    @QtCore.pyqtSlot(str, result=str)
    def web_update_token(self, uid):
        try:
            engine = self._get_engine(uid)
            if engine is None:
                return 'CONNECTION_UNKNOWN'
            server_url = engine.get_server_url()
            url = self._get_authentication_url(server_url) + '&' + urlencode({'updateToken': True})
            callback_params = {
                'engine': engine,
            }
            log.debug('Opening login window for token update with URL %s', url)
            self._open_authentication_dialog(url, callback_params)
            return ''
        except:
            log.exception('Unexpected error while trying to open web authentication window for token update')
            return 'CONNECTION_UNKNOWN'

    def _open_authentication_dialog(self, url, callback_params):
        api = WebAuthenticationApi(self, callback_params)
        dialog = WebAuthenticationDialog(QtCore.QCoreApplication.instance(), url, api)
        dialog.setWindowModality(QtCore.Qt.NonModal)
        dialog.show()

    def _get_authentication_url(self, server_url):
        token_params = {
            'deviceId': self._manager.get_device_id(),
            'applicationName': self._manager.get_appname(),
            'permission': TOKEN_PERMISSION,
        }
        device_description = DEVICE_DESCRIPTIONS.get(sys.platform)
        if device_description:
            token_params['deviceDescription'] = device_description
        return server_url + DRIVE_STARTUP_PAGE + '?' + urlencode(token_params)

    @QtCore.pyqtSlot(result=str)
    def get_new_local_folder(self):
        try:
            return self._new_local_folder
        except Exception as e:
            log.exception(e)

    @QtCore.pyqtSlot(str)
    def set_new_local_folder(self, local_folder):
        try:
            self._new_local_folder = local_folder
        except Exception as e:
            log.exception(e)

    @QtCore.pyqtSlot(result=str)
    def get_account_creation_error(self):
        try:
            return self._account_creation_error
        except Exception as e:
            log.exception(e)

    @QtCore.pyqtSlot(str)
    def set_account_creation_error(self, error):
        try:
            self._account_creation_error = error
        except Exception as e:
            log.exception(e)

    @QtCore.pyqtSlot(result=str)
    def get_token_update_error(self):
        try:
            return self._token_update_error
        except Exception as e:
            log.exception(e)

    @QtCore.pyqtSlot(str)
    def set_token_update_error(self, error):
        try:
            self._token_update_error = error
        except Exception as e:
            log.exception(e)

    @QtCore.pyqtSlot(result=str)
    def get_proxy_settings(self):
        try:
            result = dict()
            settings = self._manager.get_proxy_settings()
            result["url"] = settings.to_url(with_credentials=False)
            result["config"] = settings.config
            result["type"] = settings.proxy_type
            result["server"] = settings.server
            result["username"] = settings.username
            result["authenticated"] = (settings.authenticated == 1)
            result["password"] = settings.password
            result["port"] = settings.port
            return self._json(result)
        except Exception as e:
            log.exception(e)
            return ""

    @QtCore.pyqtSlot(str, str, str, str, str, result=str)
    def set_proxy_settings(self, config='System', server=None,
                 authenticated=False, username=None, password=None):
        try:
            config = str(config)
            url = str(server)
            settings = ProxySettings(config=config)
            if config == "Manual":
                settings.from_url(url)
            settings.authenticated = "true" == authenticated
            settings.username = str(username)
            settings.password = str(password)
            self._manager.set_proxy_settings(settings)
        except Exception as e:
            log.exception(e)
        return ""


class WebSettingsDialog(WebDialog):
    '''
    classdocs
    '''
    def __init__(self, application, section, api=None):
        '''
        Constructor
        '''
        self._section = section
        if api is None:
            api = WebSettingsApi(application)
        super(WebSettingsDialog, self).__init__(application, "settings.html",
                                                 api=api,
                                                title=Translator.get("SETTINGS_WINDOW_TITLE"))

    def set_section(self, section):
        self._section = section
        self._view.reload()
