# django-ldap3-auth


Installation:

1. Place this File into lib/ `or anywhere else`

2. In settings.py:
```python
AUTHENTICATION_BACKENDS = [
    'lib.Ldap3AuthBackend.Ldap3AuthBackend',
    # ^------------- or anywhere else
    'django.contrib.auth.backends.ModelBackend',
    # '...',
]
```

#### What this Backend does:

1. It tries to bind and whoami to <LDAP_HOST> with given Credentials
2. It searches in <LDAP_GROUPS> for groupOfName members
3. It checks if user is in one of these members lists
3. It syncs the groups to Database
4. It assigns the appropriate group(s) to user


If no user exists in db - it will be created


#### One of the following Configurations must be set

##### 1. Configfile - only with appropriate config Class (TODO)
A Configfile just as
```json
{
  "ldap-auth": {
    "host": "...",
    "port": 389,
    "base_dn": "...",
    "users_basedn": "...",
    "groups_dn": "..."
  }
}
```


##### 2. in settings.py
```python
LDAP_AUTH_HOST = '...'
LDAP_AUTH_GROUP_DN = '...'
LDAP_AUTH_USER_BASEDN = '...'
LDAP_AUTH_PORT = 389
```

##### 3. ENV Vars
```bash
export LDAP_AUTH_HOST='...'
export LDAP_AUTH_GROUP_DN='...'
export LDAP_AUTH_USER_BASEDN='...'
export LDAP_AUTH_PORT=389
```
or sourced from somewhere
