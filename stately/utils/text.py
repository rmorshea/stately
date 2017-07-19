import re
import types
import inspect
import textwrap


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Object Representations  - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def fullname(cls, attr=None):
    name = cls.__module__ + "." + cls.__name__
    if attr is not None:
        name += "." + attr
    return name


def describe(article, value, name=None, verbose=False, capital=None):
    """Return string that describes a value

    Parameters
    ----------
    article: str or None
        A definite or indefinite article. If the article is
        indefinite (i.e. "a" or "an") the appropriate one
        will be infered. Thus, the arguments of ``describe``
        can themselves represent what the resulting string
        will actually look like. If None, then no article
        will be prepended to the result. For non-articled
        description, values that are instances are treated
        definitely, while classes are handled indefinitely.
    value: any
        The value which will be named.
    name: str or None (default: None)
        Only applies when ``article`` is "the" - this
        ``name`` is a definite reference to the value.
        By default one will be infered from the value's
        type and repr methods.
    verbose: bool (default: False)
        Whether the name should be concise or verbose. When
        possible, verbose names include the module, and/or
        class name where an object was defined.
    capital: bool (default: False)
        Whether the first letter of the article should
        be capitalized or not. By default it is not.

    Examples
    --------

    Indefinite description:

    >>> describe("a", object())
    'an object'
    >>> describe("a", object)
    'an object'
    >>> describe("a", type(object))
    'a type'
    
    Definite description:

    >>> describe("the", object())
    "the object at '0x10741f1b0'"
    >>> describe("the", object)
    "the type 'object'"
    >>> describe("the", type(object))
    "the type 'type'"

    Definitely named description:

    >>> describe("the", object(), "I made")
    'the object I made'
    >>> describe("the", object, "I will use")
    'the object I will use'
    """
    if capital is None and article is not None:
        capital = article[0].lower() != article[0]

    if isinstance(article, str):
        article = article.lower()

    typename = type(value).__name__
    if verbose:
        typename = _prefix(type(value)) + typename

    if article == "the" or (article is None and not inspect.isclass(value)):
        if name is not None:
            result = "%s %s" % (typename, name)
            if article is not None:
                return add_article(result, True, capital)
            else:
                return result
        else:
            tick_wrap = False
            if inspect.isclass(value):
                name = _prefix(value) + value.__name__
            elif isinstance(value, types.FunctionType):
                name = _prefix(value) + value.__name__
                tick_wrap = True
            elif isinstance(value, types.MethodType):
                name = _prefix(value) + value.__func__.__name__
                tick_wrap = True
            elif type(value).__repr__ in (object.__repr__, type.__repr__):
                name = "at '%s'" % hex(id(value))
            else:
                name = repr(value)
            if tick_wrap:
                name = name.join("''")
            return describe(article, value, name=name,
                verbose=verbose, capital=capital)
    elif article in ("a", "an") or article is None:
        if inspect.isclass(value):
            typename = value.__name__
        if article is None:
            return typename
        return add_article(typename, False, capital)
    else:
        raise ValueError("The 'article' argument should "
            "be 'the', 'a', 'an', or None not %r" % article)

    
def _prefix(value):
    if isinstance(value, types.MethodType):
        name = describe(None, value.__self__, verbose=True) + '.'
    else:
        module = inspect.getmodule(value)
        if module is not None and module.__name__ != "builtins":
            name = module.__name__ + '.'
        else:
            name = ""
    return name


def add_article(name, definite=False, capital=False):
    """Returns the string with a prepended article.

    The input does not need to begin with a charater.

    Parameters
    ----------
    definite: bool (default: False)
        Whether the article is definite or not.
        Indefinite articles being 'a' and 'an',
        while 'the' is definite.
    capital: bool (default: False)
        Whether the added article should have
        its first letter capitalized or not.
    """
    if definite:
        result = "the " + name
    else:
        first_letters = re.compile(r'[\W_]+').sub('', name)
        if first_letters[:1].lower() in 'aeiou':
            result = 'an ' + name
        else:
            result = 'a ' + name
    if capital:
        return result[0].upper() + result[1:]
    else:
        return result
    return result


def describe_them(article, values, *args, **kwargs):
    if len(values) == 0:
        return []
    elif len(values) == 1:
        return [describe(article, values[0], *args, **kwargs)]
    else:
        return [describe(article, v, *args, **kwargs) for v in values]


def conjunction(junction, *texts):
    if len(texts) > 1:
        return ", ".join(texts[:-1]) + ", %s %s" % (junction, texts[-1])
    elif len(texts) == 1:
        return texts[0]
    else:
        return ""


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Paragraph Manipulations - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def indent(text, spaces=4, tabs=1, clean=False):
    if "\n" in text:
        return "\n".join(indent(line, spaces, tabs, clean) for line in text.split("\n"))
    elif clean:
        text = re.match(r"(?: *)(.*)", text).groups()[0]
    return " "*(spaces*tabs) + text


def dedent(text, spaces=4, tabs=1, total=False):
    if "\n" in text:
        return "\n".join(dedent(line, spaces, tabs, total) for line in text.split("\n"))
    else:
        space, text = re.match(r"( *)(.*)", text).groups()
    if not total:
        return space[spaces*tabs:] + text
    else:
        return text

def wrap_paragraphs(text, width=80):
    paragraphs = text.split("\n\n")
    wrapped = (textwrap.wrap(p) for p in paragraphs)
    return "\n\n".join("\n".join(w) for w in wrapped)