#!/usr/bin/env python

# -*- coding: iso-8859-1 -*-
__version__ = "$Revision: 0.2 $"
__author__ = "Pierrick Terrettaz"
__date__ = "2010-02-21"


import sys
import os
import urllib, urllib2
import base64
from optparse import OptionParser
import getpass

class Twitter:

    def __init__(self):
        self.conf_path = os.path.expanduser('~/.twittick/twittick.cfg')
        self.credentials = None
        
    def login(self):
        if self.credentials:
            return
        if not self.load_credentials():
            username = self.read_value('enter username')
            password = self.read_value('and password', True)            
            self.credentials = base64.encodestring('%(username)s:%(password)s' % locals())[:-1]
            if self.read_value('Save preferences ? (y/n)') == 'y':
                self.save_conf()        

    def save_conf(self):
        if not os.path.exists(self.conf_path):
            dirpath = os.path.dirname(self.conf_path)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
        open(self.conf_path, 'w').write(self.credentials)
        print 'Preferences saved in "%s"' % self.conf_path
    
    def remove_conf(self):
        if os.path.exists(self.conf_path):
            os.remove(self.conf_path)
    
    def load_credentials(self):
        if not os.path.exists(self.conf_path):
            return False
        self.credentials = open(self.conf_path).readline()
        return True
        
    def update_status(self, status=None):
        if not status:
            status = self.read_value('Enter your status')
        
        if status.strip() != '':
            self.request('http://twitter.com/statuses/update.json', {'status':status}, True)
        else:
            print 'Status is empty, nothing sent'
    
    def print_user_tweets(self, username):
        self.print_statuses(self.load_user_tweets(username))

    def print_home_timeline(self):
        self.print_statuses(self.load_home_timeline())

    def live(self, delay=60):
        import time
        notifier = TwitterNotifier()
            
        displayed = []
        while True:
            data = filter(lambda x: x['id'] not in displayed, self.load_home_timeline())
            self.print_statuses(data)
            if notifier.ready and len(data) > 0:
                n = notifier.notify('Twittick', '%d new tweets' % len(data))
            map(lambda x: displayed.append(x['id']), data)
            time.sleep(int(delay))
        
    def print_statuses(self, statuses):
        if len(statuses) > 0:
            print '\n---- %d tweets ----' % len(statuses)
        for status in statuses[::-1]: #reverse order
            self.print_status(status)
    
    def print_status(self, status):
         ret  = ' %s - %s\n' % (status['user']['name'], status['created_at'])
         ret += '  %s\n' % status['text']
         ret += '---'
         print ret

    def load_home_timeline(self):
        return self.from_json(self.request('http://api.twitter.com/1/statuses/home_timeline.json', login=True))

    def load_user_tweets(self, username):
        return self.from_json(self.request('http://api.twitter.com/1/statuses/user_timeline.json?screen_name=%s' % username, login=True))

    def from_json(self, string):
        message = 'Install simplejson python module or install python version 2.6'
        try:
            import simplejson as json            
        except ImportError:
            try:
                import json
            except ImportError:
                print message
                sys.exit(1)
        return json.loads(string)
    
    def request(self, url, data=None, login=False):
        req = urllib2.Request(url)
        if login:
            self.login()
            req.add_header("Authorization", "Basic %s" % self.credentials)

        if data:
            req.add_data(urllib.urlencode(data))
        try:
            return urllib2.urlopen(req).read()
        except urllib2.HTTPError, e:
            if e.__str__().find('Unauthorized') != -1:
                print 'username or password are incorrect'
            else:
                print e
                
            sys.exit(1)
        
    def read_value(self, message, secure=False):
        message=' > %s: ' % message
        if secure:
            return getpass.getpass(message)
        return raw_input(message)

class TwitterNotifier:
    
    def __init__(self):
        self.icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'twitter-icon.png')
        if not os.path.exists(self.icon_path):
            self.icon_path = None

        if self._init_growl():
            self.ready = True
        elif self._init_pynotify():
            self.ready = True
        else:
            self.ready = False
    
    def notify(self, title, body):
        notifier = getattr(self, "_notify_%s" % self.system)
        notifier(title, body)
    
    def _init_growl(self):
        try:
            import Growl
            self.system = 'growl'
            
            icon = Growl.Image.imageFromPath(self.icon_path)
            self.growl_notifier = Growl.GrowlNotifier('Twittick', ['tweet'], applicationIcon=icon)
            self.growl_notifier.register()
            return True
        except ImportError:
            return False
    
    def _init_pynotify(self):
        try:
            import pynotify
            self.system = 'pynotify'
            return pynotify.init("Twittick notifications")
        except ImportError:
            return False
    
    def _notify_growl(self, title, body):
        self.growl_notifier.notify('tweet', title, body)
        
    def _notify_pynotify(self, title, body):    
        import pynotify
        n = pynotify.Notification(title, body, self.icon_path)
        n.set_urgency(pynotify.URGENCY_LOW)
        n.set_timeout(1000) # 10 seconds
        n.show()
            
class CommandParser:
    
    def __init__(self, usage_text='%s command [options]' % os.path.basename(sys.argv[0])):
        self.commands = {}
        self.command_ranking = []
        self.usage_text = usage_text
        self.biggest_name = 0
        self.default = None
        
    def add_command(self, name, help, callback, options_parser = OptionParser(add_help_option=False, usage=''), default=False):
        self.commands[name] = {
            'help': help,
            'callback': callback,
            'options_parser':options_parser}
        self.command_ranking.append(name)
        if default:
            self.default = name
        
        if len(name) > self.biggest_name:
            self.biggest_name = len(name)
    
    def parse_args(self, args=None):
        if not args:
            args = sys.argv[1:]

        if len(args) == 0 and self.default:
            args = [self.default]
        elif len(args) == 0 or '--help' in args:
            self.usage()
        
        c = args.pop(0)         
        if not self.commands.has_key(c):
            self.usage()

        command = self.commands[c]
        command['callback'](*args)
        
        
    def usage(self):
        print self.usage_text
        print ''
        print 'Commands'
        for name in self.command_ranking:
            command = self.commands[name]
            if self.default == name:
                default = ' (default)'
            else:
                default = ''
            print '   %s:%s%s%s' % (name, ' ' * (2 + self.biggest_name - len(name)), command['help'], default)
            command['options_parser'].parse_args(['asd'])
            command['options_parser'].print_help()
        
        sys.exit(1)
        
if __name__ == '__main__':
    
    twitter = Twitter()
    
    cp = CommandParser()
    cp.add_command('home', 'Display home timeline', callback=twitter.print_home_timeline, default=True)
    cp.add_command('live', 'Display live home timeline', callback=twitter.live)
    cp.add_command('user', 'Display user timeline: user username', callback=twitter.print_user_tweets)
    cp.add_command('update', 'Update your status: update ["status message"]', callback=twitter.update_status)
    cp.add_command('remove-conf', 'Remove configuration file', callback=twitter.remove_conf)

    try:
        cp.parse_args()
    except KeyboardInterrupt:
        pass
