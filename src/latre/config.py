#!/usr/bin/env python3

import os.path

appname = 'Lá Tre'
version = '0.3.0'
package = 'latre'
parentloc = '/usr'
userloc = os.path.expanduser('~')
data_dir = os.path.join(parentloc, 'share', package)
userdata_dir = os.path.join(userloc, '.local', 'share', package)
dbfile = os.path.join(userdata_dir, package + '.db')
