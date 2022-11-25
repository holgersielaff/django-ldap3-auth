import importlib
import os
import sys

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import Group, User

"""

Installation:

> mkdir -p lib

Place this FIle into lib/ ore anywhere else

In settings.py:

AUTHENTICATION_BACKENDS = [
    'lib.Ldap3AuthBackend.Ldap3AuthBackend',
    'django.contrib.auth.backends.ModelBackend',
    '...',
]

######################################
What this Backend does:
+------------------------------+

1. It tries to bind and whoami to <LDAP_HOST> with given Credentials
2. It searches in <LDAP_GROUPS> for groupOfName members
3. It checks if user is in one of these members lists
3. It syncs the groups to Database
4. It assigns the appropriate group(s) to user


If no user exists in db - it will be created

####################################################


One of the following Configurations must be set

1. Configfile
+------------------------------+
A Configfile just as

{
  "ldap-auth": {
    "host": "...",
    "port": 389,
    "base_dn": "...",
    "users_basedn": "...",
    "groups_dn": "..."
  }
}


2. in settings.py
+------------------------------+
LDAP_AUTH_HOST = '...'
LDAP_AUTH_GROUP_DN = '...'
LDAP_AUTH_USER_BASEDN = '...'
LDAP_AUTH_PORT = 389

3. ENV Vars
+------------------------------+
export LDAP_AUTH_HOST='...'
export LDAP_AUTH_GROUP_DN='...'
export LDAP_AUTH_USER_BASEDN='...'
export LDAP_AUTH_PORT=389

or sourced from somewhere
"""

try:
    from lib.config import config as cfg

    config = {
        'host': cfg.ldap.host,
        'port': cfg.ldap.port or 389,
        'groupdn': cfg.ldap.groups_dn,
        'userbasedn': cfg.ldap.users_basedn,
    }
except (ModuleNotFoundError, ImportError):
    try:
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
        settings = importlib.import_module(settings_module)
        config = {
            'host': settings.LDAP_AUTH_HOST,
            'port': 389,
            'groupdn': settings.LDAP_AUTH_GROUP_DN,
            'userbasedn': settings.LDAP_AUTH_USER_BASEDN,
        }
        try:
            config['port'] = settings.LDAP_AUTH_PORT
        except:
            pass
    except Exception as e:
        config = {
            'host': os.environ.get('LDAP_AUTH_HOST'),
            'port': os.environ.get('LDAP_AUTH_PORT', 389),
            'groupdn': os.environ.get('LDAP_AUTH_GROUP_DN'),
            'userbasedn': os.environ.get('LDAP_AUTH_USER_BASEDN'),
        }

def check_config():
    exeptions = []
    for k,v in config.items():
        if not v:
            exeptions.append(EnvironmentError(f"Config.{k} has no value"))

    if exeptions:
        raise ValueError("Not all LDAP_AUTH Params set, reffer LdapAuthBackend.py CONFIG Section for more information\n"+'\n'.join(map(str, exeptions)))

check_config()

def login(user: str, password: str):
    import ldap3

    # get existant user
    try:
        USER = User.objects.get(username=user)
        if USER.is_superuser:
            return
    except User.DoesNotExist:
        USER = None

    userbasedn = config['userbasedn']
    userdn = f"uid={user},{userbasedn}"
    groupdn = config['groupdn']

    server = ldap3.Server(config['host'])
    conn = ldap3.Connection(server, user=userdn, password=password)
    conn.bind(user)

    # Must have whoami here, to lock off locked in ldap
    whoami = conn.extend.standard.who_am_i()
    if not whoami:
        print(f"No user with {userdn}", file=sys.stderr)
        if USER:
            USER.is_staff = False
            USER.is_superuser = False
            USER.save()
        return
    # EOF whoami

    # Get all groupOfNames in appropriate Group and map to {'short groupname': 'ldap entry with list of members in in'}
    conn.search(groupdn, attributes=['member'], search_filter='(objectClass=groupOfNames)')
    groupmap = {entry.entry_dn.lstrip('o').lstrip('=').split(',')[0]: entry for entry in conn.entries}
    membersof = ''.join(map(lambda m: f'(memberOf={m.entry_dn})', groupmap.values()))

    # check if user is in group - search with basedn == userdn (REVIEW - better userbasedn?)
    conn.search(userdn, search_filter=f'(&(uid={user})(|{membersof}))', attributes=['uid', 'cn', 'sn', 'givenName', 'mail'])
    if not conn.entries:
        print(f"User with {userdn} not in '{membersof}'", file=sys.stderr)
        if USER:
            USER.is_staff = False
            USER.is_superuser = False
            USER.save()
        conn.unbind()
        return

    # create user if inexistant
    if not USER:
        user = {k: v.pop(0) for k, v in conn.entries.pop(0).entry_attributes_as_dict.items()}
        USER = User(**{
            'username': user['uid'],
            'first_name': user['givenName'],
            'last_name': user['sn'],
            'email': user['mail'],
            'is_staff': True,
            'is_active': True,
        })
        USER.save()

    # create and assign groups (sync from ldap too)
    for group, entry in groupmap.items():
        try:
            try:
                g = Group.objects.get(name=group)
            except Group.DoesNotExist:
                g = Group(name=group)
                g.save()
            if userdn in entry.entry_attributes_as_dict.get('member', {}):
                g.user_set.add(USER)
        except Exception as e:
            print(e, file=sys.stderr)
            conn.unbind()
            return
    conn.unbind()
    return USER


class Ldap3Backend(BaseBackend):
    def authenticate(self, *args, **kwargs):
        return login(user=kwargs['username'], password=kwargs['password'])

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
