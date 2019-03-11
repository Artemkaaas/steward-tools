# @author: Ryan West (ryan.west@sovrin.org)

# This script requires 4 parameters as follows:
#     pool_name   -  The name of the pool you created to attach to the Sovrin Network (pool must already exist)
#     wallet_name -  The name of the wallet containing the DID used to send ledger requests (wallet must already exist)
#     wallet_key  -  The secret key of <wallet_name>
#     signing_did -  The DID with sufficient rights to run get-validator-info (must already be in the wallet <wallet_name>)

import asyncio
import logging
import argparse
import rocksdb
import time
import datetime
from pprint import pprint
from datetime import datetime
import sys
sys.path.insert(0, '../local_ledger/')

from LocalLedger import LocalLedger, Transaction
import LedgerQuery as lq
from Transaction import Transaction

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def parseArgs():
    helpTxt = 'You may optionally place each argument, line by line, in a file, then read\
               arguments from that file as so: "python3 file.py @argumentFile.txt"'
     # ch.eck arguments
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@', epilog=helpTxt)
    parser.add_argument("pool_name", help="the pool you want to connect to.")
    parser.add_argument("wallet_name", help="wallet name to be used")
    parser.add_argument("wallet_key", help="wallet key for opening the wallet")
    parser.add_argument("signing_did", help="did used to sign requests sent to the ledger")
    parser.add_argument("start_date", help="mm/dd/yyyy time to start looking at txns")
    parser.add_argument("end_date", help="mm/dd/yyyy time to stop looking at txns, inclusive")
    return parser.parse_args()

async def loadTxnsLocally(args, startTimestamp, endTimestamp):
    l = LocalLedger("ledger_copy.db", args.pool_name, args.wallet_name, args.wallet_key, 
                          args.signing_did)
    # first updates the local ledger database
    await l.connect()
    await l.update()
    await l.disconnect()
    return lq.getTxnRange(l, startTime=startTimestamp, endTime=endTimestamp)

def printTotalFeesInPeriod(txns, txnsByType, fees, startTimestamp, endTimestamp):
    nymTxn = '1'
    attribTxn = '100'
    schemaTxn = '101'
    credDefTxn = '102'

    try: 
        totalNymCost = fees['1'] * len(txnsByType[nymTxn])
    except:
        totalNymCost = 0
    try:
        totalAttribCost = fees['100'] * len(txnsByType[attribTxn])
    except:
        totalAttribCost = 0
    try:
        totalSchemaCost = fees['101'] * len(txnsByType[schemaTxn])
    except:
        totalSchemaCost = 0
    try:
        totalCredDefCost = fees['102'] * len(txnsByType[credDefTxn]) 
    except:
        totalCredDefCost = 0
    totalCost = totalNymCost + totalAttribCost + totalSchemaCost + totalCredDefCost

    startTimeStr = str(datetime.utcfromtimestamp(startTimestamp).strftime('%m/%d/%Y %H:%M:%S'))
    endTimeStr = str(datetime.utcfromtimestamp(endTimestamp).strftime('%m/%d/%Y %H:%M:%S'))

    # only list amounts if they are > 0
    print('Period: ' + startTimeStr + ' to ' + endTimeStr) 
    print('Number of transactions in range:', len(txns), '\tTotal fees to be collected:', totalCost)
    if nymTxn in txnsByType:
        print('\tNym txns:', str(len(txnsByType[nymTxn])), '\t\t\tTotal fees to be collected:', str(totalNymCost))
    if attribTxn in txnsByType:
        print('\tAttribute txns:', str(len(txnsByType[attribTxn])), '\t\tTotal fees to be collected:', str(totalAttribCost))
    if schemaTxn in txnsByType:
        print('\tSchema txns:', str(len(txnsByType[schemaTxn])), '\t\tTotal fees to be collected:', str(totalSchemaCost))
    if credDefTxn in txnsByType:
        print('\tCredential def txns:', str(len(txnsByType[credDefTxn])), '\tTotal fees to be collected:', str(totalCredDefCost))
       

def outputBillsFile(startTimestamp, endTimestamp, bills):
    startTimeStr = str(datetime.utcfromtimestamp(startTimestamp).strftime('%m-%d-%Y'))
    endTimeStr = str(datetime.utcfromtimestamp(endTimestamp).strftime('%m-%d-%Y'))

    filename = 'billing ' + startTimeStr + ' to ' + endTimeStr + '.csv'
    with open(filename, 'w') as f:
        for key, value in bills.items():
            f.write(str(key) + ',' + str(value) +  '\n')

    print('Billing by did written to \'' + filename + '\'.')
        

async def main():

    args = parseArgs()

    # TODO: verify timezone correctness
    startTimestamp = time.mktime(datetime.strptime(args.start_date, "%m/%d/%Y").timetuple())
    endTimestamp = time.mktime(datetime.strptime(args.end_date, "%m/%d/%Y").timetuple())

    # all transactions in the specified range
    txns = await loadTxnsLocally(args, startTimestamp, endTimestamp)
    
    # transactions separated by type in the format key: type, val: list(txns)
    txnsByType = {}
    # dict of all DIDs who owe money for the current period in the form key: did, val: amount
    bills = {}
    # dict of how much each transaction type currently costs
    fees = {}

    # hardcoded for now, these are only example prices; get fee amounts from the ledger later

    fees['1'] = 10
    fees['100'] = 10
    fees['101'] = 50
    fees['102'] = 25
   
   
    for t in txns.values():
        # populate txnsByType dict
        if t.getType() not in txnsByType:
            txnsByType[t.getType()] = [t]
        else:
            txnsByType[t.getType()].append(t)

        # populate bills dict
        if t.getSenderDid() not in bills:
            bills[t.getSenderDid()] = fees[t.getType()]
        else:
            bills[t.getSenderDid()] += fees[t.getType()]

    printTotalFeesInPeriod(txns, txnsByType, fees, startTimestamp, endTimestamp)
    outputBillsFile(startTimestamp, endTimestamp, bills)
    
    #for t in txnsByType['102']:
    #    print('\n\n')
    #    t.printKeys()


if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
