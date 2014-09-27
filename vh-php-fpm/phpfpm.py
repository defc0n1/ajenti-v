import os

from ajenti.api import *
from ajenti.plugins.services.api import ServiceMultiplexor
from ajenti.plugins.vh.api import ApplicationGatewayComponent, SanityCheck, Restartable
from ajenti.plugins.vh.processes import SupervisorRestartable
from ajenti.util import platform_select


TEMPLATE_CONFIG_FILE = """
[global]
pid = %(pidfile)s
error_log = /var/log/php5-fpm.log

[global-pool]
user = www-data
group = www-data

listen = /var/run/php-fcgi.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

pm = dynamic
pm.start_servers = 1
pm.max_children = 5
pm.min_spare_servers = 1
pm.max_spare_servers = 5

%(pools)s
"""

TEMPLATE_POOL = """
[%(name)s]
user = %(user)s
group = %(group)s

listen = /var/run/ajenti-v-php-fcgi-%(name)s.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660

pm = %(pm)s
pm.max_children = %(max)s
pm.start_servers = %(min)s
pm.min_spare_servers = %(sp_min)s
pm.max_spare_servers = %(sp_max)s

%(php_extras)s
"""


fpm_service_name = platform_select(
    debian='php5-fpm',
    default='php-fpm',
)


@plugin
class FPMServiceTest (SanityCheck):
    def __init__(self):
        self.type = _('PHP-FPM service')

    def check(self):
        return ServiceMultiplexor.get().get_one(fpm_service_name).running


@plugin
class PHPFPM (ApplicationGatewayComponent):
    id = 'php-fcgi'
    title = 'PHP FastCGI'

    def init(self):
        self.config_file = platform_select(
            debian='/etc/php5/fpm/php-fpm.conf',
            centos='/etc/php-fpm.conf',
            arch='/etc/php/php-fpm.conf',
        )

    def __generate_pool(self, location, backend, name):
        pm_min = backend.params.get('pm_min', 1) or 1
        pm_max = backend.params.get('pm_max', 5) or 5
        user = backend.params.get('user', 'www-data') or 'www-data'
        group = backend.params.get('group', 'www-data') or 'www-data'

        extras = ''

        for l in (backend.params.get('php_admin_values', None) or '').splitlines():
            if '=' in l:
                k, v = l.split('=', 1)
                extras += 'php_admin_value[%s] = %s\n' % (k.strip(), v.strip().strip(';'))

        for l in (backend.params.get('php_flags', None) or '').splitlines():
            if '=' in l:
                k, v = l.split('=', 1)
                extras += 'php_flag[%s] = %s\n' % (k.strip(), v.strip())

        return TEMPLATE_POOL % {
            'name': name,
            'min': pm_min,
            'max': pm_max,
            'user': user,
            'group': group,
            'pm': backend.params.get('pm', None) or 'dynamic',
            'sp_min': min(2, pm_min),
            'sp_max': min(6, pm_max),
            'php_extras': extras,
        }

    def __generate_website(self, website):
        r = ''
        for location in website.locations:
            if location.backend.type == 'php-fcgi':
                r += self.__generate_pool(location, location.backend, location.backend.id)
        return r

    def create_configuration(self, config):
        if os.path.exists(self.config_file):
            os.unlink(self.config_file)
        cfg = TEMPLATE_CONFIG_FILE % {
            'pidfile': platform_select(
                debian='/var/run/php5-fpm.pid',
                arch='/var/run/php-fpm.pid',
                centos='/var/run/php-fpm/php-fpm.pid',
            ),
            'pools': '\n'.join(self.__generate_website(_) for _ in config.websites if _.enabled)
        }
        open(self.config_file, 'w').write(cfg)

    def apply_configuration(self):
        PHPFPMRestartable.get().schedule()

    def get_checks(self):
        return [FPMServiceTest.new()]


@plugin
class PHPFPMRestartable (Restartable):
    def restart(self):
        s = ServiceMultiplexor.get().get_one(fpm_service_name)
        print fpm_service_name, s, s.running
        if not s.running:
            s.start()
        else:
            s.restart()
