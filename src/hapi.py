#!/usr/bin/env python

import os
import shlex
import logging
import subprocess
import ConfigParser
from debian import deb822

from flask import Flask
from flask.ext import restful


settings_file = './hapi.ini'
log_file = './hapi.log'


logging.basicConfig(filename=log_file, level=logging.DEBUG)

app = Flask(__name__)
api = restful.Api(app)


###
# teh code
#

def read_settings():
    """
    Returns a dict with the settings.
    params: nil
    return: dict
    """
    settings_dict = {}

    config = ConfigParser.ConfigParser()
    config.readfp(open(settings_file))

    for sect in config.sections():
        if sect not in settings_dict.keys():
            settings_dict[sect] = {}

        for opt in config.options(sect):
            if opt not in settings_dict[sect].keys():
                try:
                    settings_dict[sect][opt] = config.get(sect, opt)
                except:
                    settings_dict[sect][opt] = None

    return settings_dict


def cmp_versions(ver1, ver2):
    """
    Compares Debian package versions
    params: (str)ver1, (str)ver2
    returns: (bool)
    """
    result = False
    if ver1 and ver2:
        dpkg_cmp_cmd = "dpkg --compare-versions %s lt %s" % (ver1, ver2)
        p = subprocess.Popen(shlex.split(dpkg_cmp_cmd),
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        p.wait()
        p.communicate()

        result = p.returncode

    return result


def find_packages_files(basepath=None):
    """
    Finds Packages files within repository structure.
    params: (str)filename
    returns: (list)filepath
    """
    package_files = []
    if basepath:
        bp_content = os.walk(basepath)
        result = []
        for dirpath, dirnames, filenames in bp_content:
            if filenames:
                filenames = filter(lambda f: f.endswith('Packages'), filenames)
                for f in filenames:
                    package_files.append( os.path.join(dirpath, f) )

    return package_files


def parse_packages_file(pkg_file=None):
    """
    Parses a Package file content.
    params: (str)filename
    returns: nil
    yield: (obj)Debian package content.
    """
    for package in deb822.Packages.iter_paragraphs(open(pkg_file)):
        yield package


def prepare_dict(packages_files=None):
    """
    Prepares dicts with the Packages+Dists
    params: (list)List of Packages.
    returns: dicts
    """
    package_dict = {}

    if packages_files:
        for pkg in packages_files:
            dist_data = pkg.replace(DISTS_PATH, '').lstrip('/').rstrip('/')
            dist_data_list = dist_data.split('/')
            # if len == 5 then debian-installer.
            if len(dist_data_list) == 4:
                release, distribution, arch, foobar = dist_data_list
                # we only need (i386|amd64)
                arch = arch.replace('binary-','')

                if release not in package_dict.keys():
                    package_dict[release] = {}
                if distribution not in package_dict[release].keys():
                    package_dict[release][distribution] = {}
                if arch not in package_dict[release][distribution].keys():
                    package_dict[release][distribution][arch] = {'file':dist_data,
                                                                 'packages':{}}

    return package_dict


def populate_dist_dict(package_dict=None):
    """
    Prepares dist_dicts with the Packages+Dists
    params: (list)List of Packages.
    returns: dicts
    """

    for rel in package_dict:
        for dist in package_dict[rel]:
            for arch in package_dict[rel][dist]:
                rel_file = os.path.join(DISTS_PATH, package_dict[rel][dist][arch]['file'])
                for p in parse_packages_file(rel_file):
                    package_dict[rel][dist][arch]['packages'][p['Package']] = p.__dict__['_Deb822Dict__dict']

    return package_dict


def populate_arch_dict(packages_files=None):
    """
    Prepares dist_dicts with the Packages+Dists
    params: (list)List of Packages.
    returns: dicts
    """
    arch_dict = {}

    if packages_files:
        for pkg in packages_files:
            for p in parse_packages_file(pkg):
                if p.get('Architecture') not in arch_dict.keys():
                    arch_dict[p.get('Architecture')] = {p.get('Package'): {p.get('Version'): p.__dict__['_Deb822Dict__dict']} }
                else:
                    if p.get('Package') not in arch_dict[p.get('Architecture')].keys():
                        arch_dict[p.get('Architecture')][p.get('Package')] = {}

                    if p.get('Version') not in arch_dict[p.get('Architecture')][p.get('Package')].keys():
                        arch_dict[p.get('Architecture')][p.get('Package')][p.get('Version')] = p.__dict__['_Deb822Dict__dict']

    return arch_dict


def populate_deb_dict(packages_files=None):
    """
    Prepares deb_dicts with the Packages+Dists
    params: (list)List of Packages.
    returns: dicts
    """
    deb_dict = {}

    if packages_files:
        for pkg in packages_files:
            for p in parse_packages_file(pkg):
                if p.get('Package') not in deb_dict.keys():
                    deb_dict[p.get('Package')] = {}

                if p.get('Version') not in deb_dict[p.get('Package')].keys():
                    deb_dict[p.get('Package')][p.get('Version')] = p.__dict__['_Deb822Dict__dict']

    return deb_dict


def populate_ver_dict(packages_files=None):
    """
    Prepares deb_dicts with the Packages+Dists
    params: (list)List of Packages.
    returns: dicts
    """
    ver_dict = {}

    if packages_files:
        for pkg in packages_files:
            for p in parse_packages_file(pkg):
                if p.get('Package') not in ver_dict.keys():
                        ver_dict[p.get('Package')] = {"version": p.get('Version'),
                                                      "info": INFO_URL + p.get('Package'),
                                                      "deb": REPO_URL + p.get('Filename')}
                else:
                    ver1 = ver_dict[p.get('Package')]['version']
                    ver2 = p.get('Version')

                    cmp_ver = cmp_versions(ver1, ver2)
                    if cmp_ver == 0:
                        ver_dict[p.get('Package')] = {"version": p.get('Version'),
                                                      "info": INFO_URL + p.get('Package'),
                                                      "deb": REPO_URL + p.get('Filename')}

    return ver_dict


###
# teh data
#

SETTINGS = read_settings()
DISTS_PATH = SETTINGS['repository'].get('dists')
REPO_URL = SETTINGS['url'].get('repo')
INFO_URL = SETTINGS['url'].get('info')
packages_files = find_packages_files(SETTINGS['repository'].get('dists'))
package_dict = prepare_dict(packages_files)
dist_dict = populate_dist_dict(package_dict)
arch_dict = populate_arch_dict(packages_files)
deb_dict = populate_deb_dict(packages_files)
ver_dict = populate_ver_dict(packages_files)


###
# teh api
#

class Home(restful.Resource):
    def get(self):
        return {'packages':'/package/<pkg_name>',
                'distributions':'/dist/<release>/<dist>/<arch>',
                'architecture':'/arch/<arch>',
                'version':'/version/<arch>'
        }


class Deb(restful.Resource):
    def get(self, pkg=None):
        status = deb_dict
        if pkg:
            try:
                status = deb_dict[pkg]
            except KeyError:
                pass

        return status


class Dist(restful.Resource):
    def get(self, release=None, distribution=None, arch=None):
        status = {}
        if release:
            status = dist_dict[release]
            if distribution:
                status = dist_dict[release][distribution]
                if arch:
                    status = dist_dict[release][distribution][arch]

        return status

class Arch(restful.Resource):
    def get(self, arch=None):
        status = arch_dict
        if arch:
            try:
                status = arch_dict[arch]
            except KeyError:
                pass

        return status


class Version(restful.Resource):
    def get(self, pkg=None):

        status = ver_dict
        if pkg:
            try:
                status = {"current_version": ver_dict[pkg]["version"],
                          "info_url": ver_dict[pkg]["info"],
                          "deb_url": ver_dict[pkg]["deb"]}
            except KeyError:
                pass

        return status


api.add_resource(Home,
                 '/')
api.add_resource(Deb,
                 '/package',
                 '/package/<string:pkg>'
                 )
api.add_resource(Dist,
                 '/dist',
                 '/dist/<string:release>',
                 '/dist/<string:release>/<string:distribution>',
                 '/dist/<string:release>/<string:distribution>/<string:arch>',
                 )
api.add_resource(Arch,
                 '/arch',
                 '/arch/<string:arch>',
                 )
api.add_resource(Version,
                 '/version',
                 '/version/<string:pkg>'
                 )

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
