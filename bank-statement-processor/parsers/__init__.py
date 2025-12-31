"""
Parser initialization
"""

from parsers.base_parser import BaseBankParser
from parsers.icici_parser import ICICIParser
from parsers.axis_parser import AXISParser
from parsers.jana_parser import JanaParser
from parsers.rbl_parser import RBLParser

__all__ = ['BaseBankParser', 'ICICIParser', 'AXISParser', 'JanaParser', 'RBLParser']
