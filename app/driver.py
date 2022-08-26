from utils import *


def main():
    """Driver function.
    """

    # $CODE contract address and start block
    contract_address = '0xbd82Cd2f7C2B8710A879580399CFbfF61c5020B9'
    start_block = 15390084

    if contract_address and start_block:
        # get data
        data = get_transfer_data(
            contract_address=contract_address, start_block=start_block)

        # transform data
        transform_data = data_transformer(data)
        print(transform_data)

        # generate stats
        stats = get_stats(transform_data)
        print(stats)

    else:
        print('Enter values into variables first.')

    # export DataFrame to CSV file
    tracker = True

    while tracker:
        ask = input(
            'Do you wish to download a CSV file of the data? [y/n]').lower()
        if ask == 'yes' or ask == 'y':
            transform_data.to_csv('data.csv', index=False)
            stats.to_csv('stats.csv', index=False)
            tracker = False
            break
        elif ask == 'no' or ask == 'n':
            print('You chose not to print.')
            break

        else:
            print('Invalid option. Try again.')
            continue


if __name__ == "__main__":
    main()
