###############################################################################
#
#      This file manages all tag related classes and encapsulates much of the
#    functionality that the rest of this evaluation script works off of.
#    It is based on a class hierarchy and most of the tag specific information
#    is contained in tag specific class attributes. This has the advantage of
#    allowing us to validate tag information as it comes into,  and is saved
#    out of objects instantiated from these classes. Additionally classes are
#    equality and set hashing is determined by functions in these classes
#    which may be dynamically changed at run time (see strict_equality() and
#    fuzzy_end_equality() class methods for examples of what this looks like)
#
#    Class hierarchy reference
#
#    [+]Tag
#       [+]DocumentTag
#       [+]AnnotatorTag
#          [+]PHITag
#             [+]NameTag
#             [+]ProfessionTag
#             [+]LocationTag
#             [+]AgeTag
#             [+]DateTag
#             [+]ContactTag
#             [+]IDTag
#             [+]OtherTag

from lxml import etree
from collections import OrderedDict


class Tag(object):
    """ Base Tag object,  implements conversion of lxml element.tag to self.name
    implements 'magic' functions like __eq__ and __hash__ based on the _get_key
    function. Also defines functions for converting tags to different formats
    like back to lxml Element classes and to just plain attribute dictionaries.
    """
    attributes = OrderedDict()

    def __init__(self, element):
        self.name = element.tag
        try:
            self.id = element.attrib['id']
        except KeyError:
            self.id = ""

    def _get_key(self):
        key = []
        for k in self.key:
            key.append(getattr(self, k).lower())
        return tuple(key)

    def _key_equality(self, other):
        return self._get_key() == other._get_key() and \
            other._get_key() == self._get_key()

    def _key_hash(self):
        return hash(self._get_key())

    def __eq__(self, other):
        return self._key_equality(other)

    def __hash__(self):
        return self._key_hash()

    @classmethod
    def strict_equality(cls):
        """  Allows tags to be switched back to default strict evaluation of
        equality as defined by their class attribute 'key.' We use these
        class methods like this because both __eq__ and __hash__ must be
        changed when we relax equality between tags.
        """
        cls.__eq__ = cls._key_equality
        cls.__hash__ = cls._key_hash

    def is_valid(self):
        for k, validp in self.attributes.items():
            try:
                # If the validating function fails throw false
                if not validp(getattr(self, k)):
                    return False
            except AttributeError:
                # Attribute is not set,  if it is in the key then
                # it is a required attribute and we return false.
                if k in self.key:
                    return False

        return True

    def toElement(self):
        element = etree.Element(self.name)
        for k, validp in self.attributes.items():
            try:
                if validp(getattr(self, k)):
                    element.attrib[k] = getattr(self, k)
                else:
                    element.attrib[k] = getattr(self, k)
                    print("WARNING: Expected attribute '%s' for tag %s was "
                          "not valid ('%s')" % (k, "<%s (%s)>" % (self.name,
                                                                  self.id),
                                                getattr(self, k)))
            except AttributeError:
                if k in self.key:
                    element.attrib[k] = ''
                    print("WARNING: Expected attribute '%s' for tag %s" %
                          (k, "<%s, %s>" % (self.name, self.id)))

        return element

    def __repr__(self):
        return "<{0}: {1}>".format(self.__class__.__name__,
                                   ", ".join(self._get_key()))

    def toXML(self):
        return etree.tostring(self.toElement(), encoding='unicode')

    def toDict(self, attributes=None):
        d = {}
        if attributes is None:
            attributes = ["name"] + [k for k, v in self.attributes.items()]

        for a in attributes:
            try:
                d[a] = getattr(self, a)
            except AttributeError:
                d[a] = None

        return d


def isint(x):
    try:
        int(x)
        return True
    except ValueError:
        return False


class AnnotatorTag(Tag):
    """ Defines the tags that model the general tags produced by annotators.
    AnnotatorTag also implements the functions that convert an annotator tag
    to a DocumentTag - a tag designed to annotate document level information
    rather than specific positional information.
    """
    attributes = OrderedDict()
    attributes["id"] = lambda v: True
    attributes["docid"] = lambda v: True
    attributes["start"] = isint
    attributes["end"] = isint
    attributes["text"] = lambda v: True

    key = ["name"]

    def __repr__(self):
        try:
            return "<{0}: {1} s:{2} e:{3}>".format(self.__class__.__name__,
                                                   ", ".join(self._get_key()),
                                                   self.start, self.end)
        except AttributeError:
            return super(Tag, self).__repr__()

    def __init__(self, element):
        super(AnnotatorTag, self).__init__(element)
        self.id = None

        for k, validp in self.attributes.items():
            if k in element.attrib.keys():
                if validp(element.attrib[k]):
                    setattr(self, k, element.attrib[k])
                else:
                    fstr = "WARNING: Expected attribute '{}' for xml element "
                    fstr += "<{} ({})>  was not valid ('{}')"
                    print(fstr.format(k, element.tag,
                                      element.attrib['id']
                                      if 'id' in element.attrib.keys() else '',
                                      element.attrib[k]))
                    setattr(self, k, element.attrib[k])

            elif k in self.key:
                fstr = "WARNING: Expected attribute '{}' for xml element "
                fstr += "<{} ('{}')>, setting to ''"
                print(fstr.format(k, element.tag, element.attrib['id']
                                  if 'id' in element.attrib.keys() else ''))

                setattr(self, k, '')

    @classmethod
    def fuzzy_end_equality(cls, distance):
        """ Set the __eq__ and __hash__ functions of the cls argument
        to be _fuzzy_end__eq__ and _fuzzy_end__hash__ as defined by this
        function. Scope in the distance paramater which allows us to set
        different number of characters that we allow the end attribute to
        shift before we no longer consider two tags equal.
        """

        def _fuzzy_end__eq__(self, other):
            self_dict = OrderedDict(zip(self.key, self._get_key()))
            other_dict = OrderedDict(zip(other.key, other._get_key()))

            self_end = int(self_dict.pop("end"))
            other_end = int(other_dict.pop("end"))

            if self_dict.values() == other_dict.values() and \
               abs(self_end - other_end) <= distance:
                return True

            return False

        def _fuzzy_end__hash__(self):
            """ Here we effectively ignore the 'end' attribute when hashing.
            Two tags with different endings will hash to the same value and
            then be handled by _fuzzy_end__eq__ when it comes time to do
            comparisons.
            """
            self_dict = OrderedDict(zip(self.key, self._get_key()))

            # if a == b then it MUST be the case that hash(a) == hash(b)
            # but if a != b then the relationship between hash(a) and hash(b)
            # does not need to be defined.
            self_dict['end'] = True
            return hash(tuple(self_dict.values()))

        cls.__eq__ = _fuzzy_end__eq__
        cls.__hash__ = _fuzzy_end__hash__

    def validate(self):
        for k, validp in self.attributes.items():
            try:
                if validp(getattr(self, k)):
                    continue
                else:
                    return False
            except AttributeError:
                if k in self.key:
                    return False

        return True

    def get_document_annotation(self):
        element = etree.Element(self.name)
        for k, v in zip(self.key, self._get_key()):
            element.attrib[k] = v
        return DocumentTag(element)

    def get_start(self):
        try:
            return int(self.start)
        except TypeError:
            return self.start

    def get_end(self):
        try:
            return int(self.end)
        except TypeError:
            return self.end


class PHITag(AnnotatorTag):
    valid_TYPE = ["PATIENT", "DOCTOR", "USERNAME", "PROFESSION", "ROOM",
                  "DEPARTMENT", "HOSPITAL", "ORGANIZATION", "STREET", "CITY",
                  "STATE", "COUNTRY", "ZIP", "OTHER", "LOCATION-OTHER", "AGE",
                  "DATE", "PHONE", "FAX", "EMAIL", "URL", "IPADDR", "SSN",
                  "MEDICALRECORD", "HEALTHPLAN", "ACCOUNT", "LICENSE",
                  "VEHICLE", "DEVICE", "BIOID", "IDNUM"]
    attributes = OrderedDict(AnnotatorTag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in PHITag.valid_TYPE

    key = AnnotatorTag.key + ["start", "end", "TYPE"]

    def _get_key(self):
        key = []
        for k in self.key:
            key.append(getattr(self, k).upper())
        return tuple(key)

    def exact_equals(self, other):
        pass

    def overlap_equals(self, other):
        pass


class NameTag(PHITag):
    valid_TYPE = ['PATIENT', 'DOCTOR', 'USERNAME']
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in NameTag.valid_TYPE


class ProfessionTag(PHITag):
    valid_TYPE = ["PROFESSION"]
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in ProfessionTag.valid_TYPE


class LocationTag(PHITag):
    valid_TYPE = ['ROOM', 'DEPARTMENT', 'HOSPITAL', 'ORGANIZATION', 'STREET',
                  'CITY', 'STATE', 'COUNTRY', 'ZIP', 'LOCATION-OTHER']
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in LocationTag.valid_TYPE


class AgeTag(PHITag):
    valid_TYPE = ['AGE']
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in AgeTag.valid_TYPE


class DateTag(PHITag):
    valid_TYPE = ['DATE']
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in DateTag.valid_TYPE


class ContactTag(PHITag):
    valid_TYPE = ['PHONE', 'FAX', 'EMAIL', 'URL', 'IPADDR']
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in ContactTag.valid_TYPE


class IDTag(PHITag):
    valid_TYPE = ['SSN', 'MEDICALRECORD', 'HEALTHPLAN', 'ACCOUNT',
                  'LICENSE', 'VEHICLE', 'DEVICE', 'BIOID', 'IDNUM']
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in IDTag.valid_TYPE


class OtherTag(PHITag):
    valid_TYPE = 'OTHER'
    attributes = OrderedDict(PHITag.attributes.items())
    attributes['TYPE'] = lambda v: v.upper() in OtherTag.valid_TYPE


PHITag.tag_types = {
    "PHI": PHITag,
    "NAME": NameTag,
    "PROFESSION": ProfessionTag,
    "LOCATION": LocationTag,
    "AGE": AgeTag,
    "DATE": DateTag,
    "CONTACT": ContactTag,
    "ID": IDTag,
    "OTHER": OtherTag}


PHI_TAG_CLASSES = [NameTag,
                   ProfessionTag,
                   LocationTag,
                   AgeTag,
                   DateTag,
                   ContactTag,
                   IDTag,
                   OtherTag]


# Comment should be last in tag order,  so add it down here
# that way all other sub tags have had their attributes set first
for c in PHI_TAG_CLASSES:
    c.attributes["comment"] = lambda v: True
