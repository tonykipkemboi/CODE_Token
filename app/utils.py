import requests
import os
import pandas as pd
import numpy as np

from dotenv import load_dotenv

load_dotenv()


def is_hexadecimal(contract_address: str) -> bool:
    """Checks if address is hexadecimal

      This function validates contract address is hexadecimal.

      Parameters
      ----------
      address: potential hexadecimal address

      Returns
      -------
      bool: True if hexadecimal, otherwise False.
    """
    # check using python int() function
    try:
        int(contract_address, 16)
        return True
    except ValueError:
        return False


def to_decimal(hexadecimal: str) -> int:
    """Converts a hexadecimal string to decimal.
    """

    hex = hexadecimal

    # conversion
    decimal = int(hex, 16)

    return decimal


def to_hexadecimal(decimal: int) -> str:
    """Converts a decimal block to hexadecimal.
    """

    if decimal > 0:
        hexadecimal = hex(decimal)

    else:
        print('Decimal value has to be greater than 0.')

    return hexadecimal


def validate_address(contract_address: str) -> str:
    """Validates contract address.

      Requirements for a valid address:
      - 40-digit hexadecimal address
      - 42-digit hexadecimal address; prefix '0x' added

      If address is in a hexidecimal format then prefix it with '0x'. 
      If address is already of leght 42, return address. 
      If address is invalid, return None

      Parameters
      ----------
      address: potential ethereum address

      Returns
      -------
      address: an address with the correct format
    """

    if contract_address:
        # check if address is in hexadecimal format
        if is_hexadecimal(contract_address):
            if len(contract_address) == 42:
                return contract_address

            if len(contract_address) == 40:
                return '0x' + contract_address

        else:
            print('Not a valid hexadecimal contract address.')

    return None


def transfers_url(contract_address: str) -> str:
    """Gets API key and returns a string ready to send payload

      API key will be stored locally in the 'env' file; .env added to .gitignore for safety.
      Access the key variable and verify it is present, else notify user to add key to .env file 
      TODO: find a better way to handle adding missing key
      Two URLS needed:
      1. to get non-SPAM nfts only; NFTs that have been classified as spam. Spam classification has a wide range 
         of criteria that includes but is not limited to emitting fake events and copying other well-known NFTs.
      2. to get all nfts including SPAM; will filter the two dataframes to isolate spammy ones.
      3. to paginate the request as the results come with a `pageKey` if more pages exist.
      4. TODO: add url to getFloorPrice of the user NFT based of the contract addresses of the ones
         user holds

      Parameters
      ----------
      address:
      pagekey:

      Returns
      -------
      str: tuples consisting of URLs to query Alchemy API 
    """

    # check API key is assigned to variable
    try:
        api_key = os.getenv('ALCHEMY_API_KEY')
        print('API Key found!')
    except KeyError:
        print('API Key not set, please add your key to .env file.')

    # check if address is valid
    valid = validate_address(contract_address)

    # url
    url = f"https://eth-mainnet.alchemyapi.io/v2/{api_key}"

    return url


def data_transformer(raw_data: list) -> pd.DataFrame:
    """Normalizes a list of raw data and returns a dataframe.
    """

    # normalize raw_data json output
    normalize = pd.json_normalize(raw_data)

    # explode transfers column holding target data
    df_raw = normalize.explode("result.transfers")

    # normalize transfer data
    df_transfers = pd.json_normalize(df_raw['result.transfers'])

    # # add 'pageKey' column to df
    # df_transfers['pageKey'] = df_raw["result.pageKey"]

    # pick out target columns
    df = df_transfers[['metadata.blockTimestamp', 'blockNum', 'from', 'to', 'value',
                       'asset', 'category', 'rawContract.address', 'hash'
                       ]]

    # rename the columns
    df = df.rename(columns={'metadata.blockTimestamp': 'timestamp',
                            'blockNum': 'blocknum',
                            'rawContract.address': 'contract_address'
                            })

    # convert 'timestamp' column to datetime[s]
    df['timestamp'] = df['timestamp'].astype('datetime64[s]')

    # convert columns from hexadecimal to decimal
    df['blocknum'] = df['blocknum'].apply(lambda x: to_decimal(x))

    # add url link to txn hash column
    df['hash'] = [f"https://etherscan.io/tx/{hash}" for hash in df['hash']]

    return df


def get_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Takes a transformed dataframe and generates percentage and ownership stats 
    by the amount of $CODE tokens claimed.

    parameters:
    -----------
    df: pandas dataframe that has been transformed by the
        `data_transformer` function

    return:
    -------
    df_percent: percentage stats of $CODE claim
    """

    # find token type percentage
    token_percentage = df['value'].value_counts(normalize=True) * 100
    df_percent = pd.DataFrame(token_percentage)

    # rename value col to %
    df_percent = df_percent.rename(columns={'value': 'percentage'})

    # count owners of $CODE by value
    category = df['value'].value_counts()

    # rename index to 'CODE'
    df_percent.index.names = ['CODE']

    # add owners to df
    df_percent['owners'] = category
    df_percent = df_percent[['owners', 'percentage']]

    # set index from range 1-n
    df_percent['index'] = range(1, len(df_percent) + 1)
    df_percent = df_percent.reset_index()
    df_percent = df_percent.set_index('index')
    df_percent['CODE'] = df_percent['CODE'].apply(np.floor)
    df_percent['percentage'] = df_percent['percentage'].apply(np.floor)

    return df_percent


def get_transfer_data(contract_address: str, start_block: int) -> list:
    """Gets asset transfers data from Alchemy by contract address.

      Parameters
      ----------
      contract_address: address of contract
      start_block: check etherscan or paste contract in
                   miniscan.xyz to find start block
      Returns
      -------
      list: json data
    """

    # transfers data container
    data = []

    # Alchemy API url
    url = transfers_url(contract_address)

    # convert start_block to hexadecimal
    start_block = to_hexadecimal(start_block)

    payload = {
        "id": 1,
        "jsonrpc": "2.0",
        "method": "alchemy_getAssetTransfers",
        "params": [
            {
                "fromBlock": "{}".format(start_block),
                "toBlock": "latest",
                "fromAddress": "{}".format(contract_address),
                "category": ["erc20"],
                "withMetadata": True,
                "excludeZeroValue": True
            }
        ]
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    def paginate(url: str, payload: list, headers: dict, data: list):
        """Takes pagekey and downloads the next page iteratively.
        """

        # get first batch of data
        print('Downloading first 1000 data points...')
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        output = response.json()
        data.append(output)

        # while output['result']['pageKey'] is not empty, download the next 1000 data points
        while "pageKey" in output['result']:
            page = output['result']['pageKey']

            if page:
                print()
                print("Next page found, downloading the next batch of data...")
                print('pageKey:', page)
                # added pagekey to payload
                payload = {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "alchemy_getAssetTransfers",
                    "params": [
                        {
                            "fromBlock": "{}".format(start_block),
                            "toBlock": "latest",
                            "fromAddress": "{}".format(contract_address),
                            "category": ["erc20"],
                            "withMetadata": True,
                            "excludeZeroValue": True,
                            "pageKey": "{}".format(page)
                        }
                    ]
                }
                response = requests.post(url, json=payload, headers=headers)
                response.raise_for_status()
                output = response.json()
                data.append(output)

            else:
                print('No more pages {}', page)
                print('----------------------')
                break

    onchain_data = paginate(url, payload, headers, data)

    return data
