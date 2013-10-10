# -*- coding: utf-8 -*-

import datetime
import json
import os
import os.path
import urllib2
import time


"""
Python API for the Intuition project.  Intuition provides localisation for tools
hosted on the Toolserver or Tool Labs.  The `Intuition` class downloads the
messages and provides them to the user.

Variables:
    `intuition`     the default intuition instance
"""

class Intuition(object):
    """
    Provides the Intuition messages.  The messages are downloaded on demand from
    Labs and cached for an hour.  The language to be set can be specified.  If not,
    it is read from a cookie.  The default language is English.  Each tool should
    use its own domain for its messages.

    Static fields:
        `COOKIE_USERLANG`           the cookie to read the language from
        `DEFAULT_TRANSLATION_PATH`  the default path to store the translations to
        `DOWNLOAD_URL`              the URL to get the messages from (to be
                                    formatted with the domain(s) and the language)
        `HOMEPAGE`                  the URL of the Intuition homepage
    """

    COOKIE_USERLANG = 'TsIntuition_userlang'

    DEFAULT_TRANSLATION_PATH = os.path.expanduser('~/intuition')

    DOWNLOAD_URL = 'https://tools.wmflabs.org/intuition/api.php?domains={}&lang={}'

    HOMEPAGE = 'https://tools.wmflabs.org/intuition/'

    def __init__(self, domain=None, language=None, translation_path=DEFAULT_TRANSLATION_PATH,
                 update_on_missing=False, cache_time=datetime.timedelta(hours=1)):
        """
        Creates a new Intuition instance.

        Arguments:
            `domain`            the default domain to get the messages for, 
                                may be `None`
            `language`          the default language, may be `None`
            `translation_path`  the path to store the translations to, may be `None`
            `update_on_missing` if `True`, the cached messages are reloaded if a
                                a key cannot be found
            `cache_time`        the `timedelta` after which cached messages expire
        """

        self.default_domain = domain
        self.default_language = language
        self.translation_path = translation_path
        self.update_on_missing = update_on_missing
        self.cache_time = cache_time

        self.language = self.init_language()
        self.domain_cache = {}

        if not os.path.exists(self.translation_path):
            os.mkdir(self.translation_path)

    def init_language(self):
        """
        Reads the langauge to use from a cookie.  If the cookie is not set, the default
        langauge is used.
        """

        cookies = os.environ['HTTP_COOKIE'].split(';')
        for cookie in cookies:
            (key, value) = cookie.split('=')
            if key = Intuition.COOKIE_USERLANG:
                return value
            
        return self.default_language

    def get(self, key, domain=None, language=None):
        """
        Returns the localized message for the given key, domain and language.  
        The domain and language may be `None` to use the default values.  If the
        domain or the key are invalid, a `ValueError` is thrown.
        """

        if domain is None:
            if self.default_domain is None:
                raise ValueError('No domain given!')
            domain = self.default_domain
        messages = self.get_domain(domain)

        if not key in messages and self.update_on_missing:
            messages = self.get_domain(domain, language, force_download=True)

        if not key in messages:
            raise ValueError('No message for that key!')

        return messages[key]        

    def get_domain(self, domain, language=None, force_download=False):
        """
        Returns the message for the given domain and language.  If no language
        is given, the default language is used.  If `force_download` is set to
        `True`, the messages are downloaded from Labs even if there are not
        expired cache values.
        """

        if language is None:
            language = self.language

        domain_present = False
        if domain in self.domain_cache:
            if language in self.domain_cache[domain]:
                if not self.is_cache_outdated(domain, language):
                    domain_present = True

        if not domain_present or force_download:
            messages = self.read_domain(domain, language, force_download)

            if not domain in self.domain_cache:
                self.domain_cache[domain] = {}
            if not language in self.domain_cache[domain]:
                self.domain_cache[domain][language] = {}
            
            self.domain_cache[domain][language]['messages'] = messages
            self.domain_cache[domain][language]['update'] = datetime.datetime.now()
        
        return self.domain_cache[domain][language]['messages']

    def read_domain(self, domain, language, force_download=False):
        """
        Reads the messages for the given domain and language from the file system
        and returns it.  If `force_download` is set to `True`, the message files
        does not exist or expired, the messages are downloaded from Labs.  If the
        domain is invalid, a `ValueError` is raised.
        """

        domain_path = '{}/{}_{}.json'.format(self.translation_path,
                                             domain, language)
        if force_download or not os.path.exists(domain_path) or self.is_file_outdated(domain_path):
            url = Intuition.DOWNLOAD_URL.format(domain, language)
            result = urllib2.urlopen(url)
            domain_file = open(domain_path, 'w')
            domain_file.write(result.read())
            domain_file.close()

        domain_file = open(domain_path, 'r')
        json_result = json.load(domain_file)
        if 'error' in json_result:
            raise Exception(json_result['error'])
        messages = json_result['messages'][domain]
        if not messages:
            raise ValueError('Illegal domain given: {}'.format(domain))

        return messages

    def is_file_outdated(self, domain_path):
        """
        Checks whether the file located at the given path expired.
        """

        last_modification = datetime.datetime.fromtimestamp(os.path.getmtime(domain_path))
        return self.is_outdated(last_modification)

    def is_cache_outdated(self, domain, language):
        """
        Checks whether the cached values for the given domain and language expired.
        Before you call this method, you have to ensure that there are cached
        values for the given domain and language.
        """

        return self.is_outdated(self.domain_cache[domain][language]['update'])

    def is_outdated(self, timestamp):
        """
        Checks whether messages retrieved at the given time expired.
        """

        expiry_time = datetime.datetime.now() - self.cache_time
        return expiry_time > timestamp


intuition = Intuition()

def get(key, domain=None, language=None):
    """
    Get a message for the given key, domain and language from the default
    Intuition instance.  If the domain or language are `None`, the default
    values are used.
    """

    return intuition.get(key, domain, language)

def init(domain, environment=None, **kwargs):
    """
    Init the default Intuition instance for the given domain and arguments.
    If a Jinja2 environment is given, the `msg` function is defined to
    provide the messages.
    """

    intuition = Intuition(domain=domain, **kwargs)

    if environment not None:
        environment.globals['msg'] = get

