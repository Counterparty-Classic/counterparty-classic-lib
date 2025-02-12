#! /usr/bin/python3

"""Destroy a quantity of an asset."""

import struct
import json
import logging
logger = logging.getLogger(__name__)

from counterpartylib.lib import util
from counterpartylib.lib import config
from counterpartylib.lib import script
from counterpartylib.lib import message_type
from counterpartylib.lib.script import AddressError
from counterpartylib.lib.exceptions import *

FORMAT = '>QQ'
LENGTH = 8 + 8
MAX_TAG_LENGTH = 34
ID = 110


def initialise(db):
    cursor = db.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS destructions(
                      tx_index INTEGER PRIMARY KEY,
                      tx_hash TEXT UNIQUE,
                      block_index INTEGER,
                      source TEXT,
                      asset INTEGER,
                      quantity INTEGER,
                      tag TEXT,
                      status TEXT,
                      FOREIGN KEY (tx_index, tx_hash, block_index) REFERENCES transactions(tx_index, tx_hash, block_index))
                   ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS
                      status_idx ON destructions (status)
                   ''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS
                      address_idx ON destructions (source)
                   ''')


def pack(db, asset, quantity, tag):
    data = message_type.pack(ID)
    if isinstance(tag, str):
        tag = bytes(tag.encode('utf8'))[0:MAX_TAG_LENGTH]
    elif isinstance(tag, bytes):
        tag = tag[0:MAX_TAG_LENGTH]
    else:
        tag = b''

    data += struct.pack(FORMAT, util.get_asset_id(db, asset, util.CURRENT_BLOCK_INDEX), quantity)
    data += tag
    return data


def unpack(db, message):
    try:
        asset_id, quantity = struct.unpack(FORMAT, message[0:16])
        tag = message[16:]
        asset = util.get_asset_name(db, asset_id, util.CURRENT_BLOCK_INDEX)

    except struct.error:
        raise UnpackError('could not unpack')

    except AssetIDError:
        raise UnpackError('asset id invalid')

    return asset, quantity, tag


def validate (db, source, destination, asset, quantity, tag):

    problems = []

    try:
        util.get_asset_id(db, asset, util.CURRENT_BLOCK_INDEX)
    except AssetError:
        problems.append('asset invalid')

    try:
        script.validate(source)
    except AddressError:
        problems.append('source address invalid')
        
    if destination:
        problems.append('destination exists')

    if asset == config.BTC:
        problems.append('cannot destroy {}'.format(config.BTC))

    if type(quantity) != int:
        problems.append('quantity not integer')

    if quantity > config.MAX_INT:
        problems.append('integer overflow, quantity too large')

    if quantity < 0:
        problems.append('quantity negative')

    if ('asset invalid' not in problems) and (util.get_balance(db, source, asset) < quantity):
        problems.append('balance insufficient')

    try:
        if type(tag) is not bytes:
            json.dumps(tag)
    except (TypeError, OverflowError):
        problems.append("cannot decode tag")

    if len(problems) > 0:
        raise ValidateError(",".join(problems))

def compose (db, source, asset, quantity, tag):
    # resolve subassets
    asset = util.resolve_subasset_longname(db, asset)

    validate(db, source, None, asset, quantity)
    data = pack(db, asset, quantity, tag)

    return (source, [], data)


def parse (db, tx, message):
    status = 'valid'

    asset, quantity, tag = None, None, None

    try:
        asset, quantity, tag = unpack(db, message)
        validate(db, tx['source'], tx['destination'], asset, quantity, tag)
        util.debit(db, tx['source'], asset, quantity, 'destroy', tx['tx_hash'])

    except UnpackError as e:
        status = 'invalid: ' + ''.join(e.args)

    except (ValidateError, BalanceError) as e:
        status = 'invalid: ' + ''.join(e.args)

    bindings = {
                'tx_index': tx['tx_index'],
                'tx_hash': tx['tx_hash'],
                'block_index': tx['block_index'],
                'source': tx['source'],
                'asset': asset,
                'quantity': quantity,
                'tag': tag,
                'status': status,
               }
    if "integer overflow" not in status:
        sql = 'insert into destructions values(:tx_index, :tx_hash, :block_index, :source, :asset, :quantity, :tag, :status)'
        cursor = db.cursor()
        cursor.execute(sql, bindings)
    else:
        if tx["block_index"] != config.MEMPOOL_BLOCK_INDEX:
            logger.warn("Not storing [destroy] tx [%s]: %s" % (tx['tx_hash'], status))
            
            bindings_dump = ""
            try:
                bindings_dump = json.dumps(bindings)
            except TypeError:
                bindings_dump = "ERROR: bindings not serializable"
                
            logger.debug("Bindings: %s" % (bindings_dump, ))


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
