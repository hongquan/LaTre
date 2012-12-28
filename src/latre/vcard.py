
import quopri

class VCard:
    def __init__(self):
        props = ('N', 'FN', 'NICKNAME', 'PHOTO', 'BDAY', 'ADR', 'LABEL', 'TEL',
                 'EMAIL', 'MAILER', 'TZ', 'GEO', 'TITLE', 'ROLE', 'LOGO', 'AGENT',
                 'ORG', 'NOTE', 'REV', 'SOUND', 'URL', 'UID', 'VERSION', 'KEY', 'VERSION')
        self.props = dict.fromkeys(props)
        self.props['TEL'] = []
        self.fullcontent = None
        self._name = None   # Used as cache for name parsing
        self._tels = None

    def __eq__(self, other):   # Use for comparing
        return self.__dict__ == other.__dict__

    @property
    def name(self):
        ''' Return tuple (lastname, firstname) '''
        if self.props['N'] is None:
            return None
        if self._name is None:
            self._name = _parse_name(self.props['N'])
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def version(self):
        return _parse_version(self.props['VERSION'])

    @version.setter
    def version(self, value):
        if _is_version_number(value):
            self.props['VERSION'] = 'VERSION:' + str(value)
        else:
            raise ValueError('{} as version is not accepted.'.format(value))

    @property
    def tels(self):
        if not self._tels:
            self._tels = [_parse_tel(t) for t in self.props['TEL']]
        return self._tels

    @tels.setter
    def tels(self, values):
        self._tels = values
        self.props['TEL'] = ['TEL;TYPE=VOICE;TYPE=CELL:' + v for v in values]

    @property
    def formatted_name(self):
        return _parse_formatted_name(self.props['FN'])

    def __str__(self):
        return 'VCard<{}>'.format(self.name)


class VCardError(Exception):
    def __init__(self, typ, desc):
        self.typ = typ
        self.desc = desc

    def __str__(self):
        return "{}: {}".format(self.typ, self.desc)


def from_string(content):
    if not content.startswith('BEGIN:VCARD'):
        raise VCardError('Format error', 'No BEGIN:VCARD.')

    if content.count('END:VCARD') != content.count('BEGIN:VCARD'):
        raise VCardError('Format error', 'There are not the same amount of END:VCARD and BEGIN:VCARD keywords.')

    # Get the vcard content of each contact (between BEGIN:VCARD and END:VCARD keywords)
    cards = []
    shift1 = len('BEGIN:VCARD')
    shift2 = len('END:VCARD')
    start = stop = 0   # Indices to get part of content
    while True:        # The file may contain multiple contacts
        start = content.find('BEGIN:VCARD', stop)
        if start == -1:
            # No more contact, stop searching
            break
        stop = content.find('END:VCARD', start + shift1)
        stop = stop + shift2;
        part = content[start:stop]
        c = parse_each(part)
        if c:
            cards.append(c)
    return cards


def from_file(filename):
    with open(filename) as fl:
        content = fl.read()
    return from_string(content.strip())


def parse_each(content):
    vcard = VCard()
    for line in content.splitlines():
        if line.startswith('VERSION:'):
            vcard.props['VERSION'] = line.strip()
        elif line.startswith('N:') or line.startswith('N;'):
            vcard.props['N'] = line.strip()
        elif line.startswith('TEL;') or line.startswith('TEL:'):
            vcard.props['TEL'].append(line)
        elif line.startswith('FN:'):
            vcard.props['FN'] = line.strip()
    return vcard

def _is_version_number(string):
    return string.replace('.', '').isdigit()

def _parse_version(line):
    ver = line[len('VERSION:'):].strip()
    if _is_version_number(ver):
        return ver
    else:
        raise VCardError('Field error', 'Illegal character in VERSION field.')

def _parse_name(line):
    line = line.rstrip(';')
    try:
        params, name = line.split(':')
    except ValueError:
        raise VCardError('Field error', 'N field: Cannot get the main string')
    # Remove N at beginning
    if params.startswith('N;'):
        params = params[2:]
    else:  # Only 'N' in params, the string is not encoded
        return _split_name(name)

    # Convert params string to dict
    params = dict([p.split('=') for p in params.split(';')])
    if params['ENCODING'] == 'QUOTED-PRINTABLE':
        # We are about decode the name string. We have to convert to bytes
        # because the quopri module does not work with string
        name = bytes(name, 'ascii')
        name = quopri.decodestring(name)
    else:
        raise VCardError('Field error',
                         'N field: {} encoding is not supported'.format(params['ENCODING']))
    if 'CHARSET' in params:
        name = name.decode(params['CHARSET'])

    return _split_name(name)

def _parse_tel(line):
    params, number = line.split(':')
    return number

def _parse_formatted_name(line):
    if line is None:
        return None
    field, string = line.split(':')
    return string

def _split_name(name):
    last, first = name.split(';')
    return (first, last)