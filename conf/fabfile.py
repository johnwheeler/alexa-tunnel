import os
import glob
from datetime import datetime

from fabric.api import *
from fabric.contrib import files
from fabric.utils import abort

env.host_string = '2localhost.com'
env.use_ssh_config = True


APP_NAME = '2localhost'
APP_MODULE = 'tolocalhost'
DEPLOY_DIR = '/var/www/html/{}'.format(APP_NAME)
LETSENCRYPT = '{}/.well-known'.format(DEPLOY_DIR)
VIRTUALENV = '{}/env'.format(DEPLOY_DIR)
LOCAL_ARCHIVE = 'dist/{}.tar.gz'.format(APP_NAME)
REMOTE_ARCHIVE = '/var/{}.tar.gz'.format(APP_NAME)


def tail(grep=""):
    sudo("tail -F -n +1 /var/log/gunicorn/{app_name}.log | grep --line-buffered -i '{grep}'" \
        .format(app_name=APP_NAME, grep=grep))


def clear_logs():
    sudo("rm -f /var/log/gunicorn/{app_name}.log".format(app_name=APP_NAME))


def dist():
    outdir = 'dist/%s' % APP_NAME
    local('mkdir -p %s' % outdir)
    local('cp -R %s %s' % (APP_MODULE, outdir))
    local('find %s -name "*.pyc" -type f -delete' % outdir)
    local('cp requirements.txt %s' % outdir)
    local('tar czf dist/%s.tar.gz %s' % (APP_NAME, outdir))


def deploy():
    dist()
    _upload_and_extract_archive()
    _update_py_deps()
    if not files.exists(LETSENCRYPT, use_sudo=True):
        sudo('mkdir %s' % LETSENCRYPT)
    sudo('chown -R root:www-data %s' % DEPLOY_DIR)
    sudo('chmod -R og-rwx,g+rxs %s' % DEPLOY_DIR)
    sudo("service gunicorn reload")
    clean()


def clean():
    local('rm -rf dist')


def clean_prod():
    sudo('rm -rf %s' % DEPLOY_DIR)


def _upload_and_extract_archive():
    put(LOCAL_ARCHIVE, REMOTE_ARCHIVE)
    if not files.exists(DEPLOY_DIR, use_sudo=True):
        sudo('mkdir %s' % DEPLOY_DIR)
    appdir = '{}/{}'.format(DEPLOY_DIR, APP_NAME)
    sudo('rm -rf {}'.format(appdir))
    sudo('tar xmzf {} -C {} --strip-components=2'.format(REMOTE_ARCHIVE, DEPLOY_DIR))
    sudo('rm {}'.format(REMOTE_ARCHIVE))


def _update_py_deps():
    if not files.exists(VIRTUALENV, use_sudo=True):
        sudo('virtualenv {}'.format(VIRTUALENV))
    sudo('{}/bin/pip install -q -r {}/requirements.txt'.format(VIRTUALENV, DEPLOY_DIR))
