# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'u206123'

import os
import pyaes
import base64
from argparse import ArgumentParser

# Shared utilities for configuration

def find_config_file_path(filename, optional=False):
    """search cimon.yaml in home dir cimon directory"""
    filewithpath = "%s/cimon/%s" % (os.path.expanduser("~"), filename)
    if os.path.isfile(filewithpath):
        return filewithpath
    elif not optional:
        raise Exception("No file %s found user home, current or application directory" % filename)

def decrypt(encrypted, key):
    if encrypted:
        if not key:
            raise Exception("No key given to decrypt password")
        aes = pyaes.AESModeOfOperationCTR(key)
        return aes.decrypt(base64.b64decode(encrypted)).decode("utf-8")

def encrypt(plaintext, key):
    if plaintext:
        if not key:
            raise Exception("No key given to encrypt password")
        aes = pyaes.AESModeOfOperationCTR(key)
        return base64.b64encode(aes.encrypt(plaintext)).decode("utf-8")

if  __name__ =='__main__':
    parser = ArgumentParser(description="Encrypt or decyrpt passwords")
    parser.add_argument("-k",  "--key", help="The password key file with its path")
    parser.add_argument("-e",  "--encrypt", help="Encrypt the given string")
    parser.add_argument("-d",  "--decrypt", help="Decrypt the given string")

    args = parser.parse_args()
    keyfile = args.key or find_config_file_path("key.bin")
    with open(keyfile, "rb") as k:
        if args.decrypt:
            print(decrypt(args.decrypt, k.read()))
        elif args.encrypt:
            print(encrypt(args.encrypt, k.read()))
        else:
            print("One of the Options encrypt or decrypt are required")
            parser.print_help()