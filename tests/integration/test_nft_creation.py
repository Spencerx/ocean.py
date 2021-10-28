#
# Copyright 2021 Ocean Protocol Foundation
# SPDX-License-Identifier: Apache-2.0
#
import json

import pytest
from ocean_lib.models.v4.erc20_token import ERC20Token
from ocean_lib.models.v4.erc721_factory import ERC721FactoryContract
from ocean_lib.models.v4.erc721_token import ERC721Token
from ocean_lib.models.v4.models_structures import ErcCreateData
from ocean_lib.web3_internal.constants import ZERO_ADDRESS
from tests.resources.helper_functions import (
    get_another_consumer_wallet,
    get_consumer_wallet,
    get_publisher_wallet,
)
from web3 import exceptions
from ocean_lib.web3_internal.wallet import Wallet
from web3 import Web3

_NETWORK = "development"


def get_nft_factory_address(config):
    """Helper function to retrieve a known ERC721 factory address."""

    # FIXME: fix get_contract_addresses bug to use here
    with open(config.address_file) as f:
        network_addresses = json.load(f)

    return network_addresses[_NETWORK][ERC721FactoryContract.CONTRACT_NAME]


def get_nft_template_address(config):
    """Helper function to retrieve a known ERC721 template address."""

    # FIXME: fix get_contract_addresses bug to use here
    with open(config.address_file) as f:
        network_addresses = json.load(f)

    return network_addresses[_NETWORK][ERC721Token.CONTRACT_NAME]["1"]


def deploy_erc721_erc20(web3, config, erc721_publisher: Wallet, erc20_minter: Wallet):
    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    tx = erc721_factory.deploy_erc721_contract(
        "NFT",
        "NFTSYMBOL",
        1,
        ZERO_ADDRESS,
        "https://oceanprotocol.com/nft/",
        erc721_publisher,
    )
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx)
    registered_event = erc721_factory.get_event_log(
        ERC721FactoryContract.EVENT_NFT_CREATED,
        tx_receipt.blockNumber,
        web3.eth.block_number,
        None,
    )
    token_address = registered_event[0].args.newTokenAddress
    erc721_token = ERC721Token(web3, token_address)

    erc_create_data = ErcCreateData(
        1,
        ["ERC20DT1", "ERC20DT1Symbol"],
        [
            erc20_minter.address,
            erc721_publisher.address,
            erc721_publisher.address,
            ZERO_ADDRESS,
        ],
        [web3.toWei("0.5", "ether"), 0],
        [b""],
    )
    tx_result = erc721_token.create_erc20(erc_create_data, erc721_publisher)
    tx_receipt2 = web3.eth.wait_for_transaction_receipt(tx_result)

    registered_event2 = erc721_factory.get_event_log(
        ERC721FactoryContract.EVENT_TOKEN_CREATED,
        tx_receipt2.blockNumber,
        web3.eth.block_number,
        None,
    )

    erc20_address = registered_event2[0].args.newTokenAddress

    erc20_token = ERC20Token(web3, erc20_address)
    return erc721_token, erc20_token


def test_erc721_roles(web3, config):
    # NFT Owner is also added as manager when deploying (first time), if transferred that doesn't apply
    publisher = get_publisher_wallet()
    consumer = get_consumer_wallet()
    another_consumer = get_another_consumer_wallet()

    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    tx = erc721_factory.deploy_erc721_contract(
        "NFT", "NFTSYMBOL", 1, ZERO_ADDRESS, "https://oceanprotocol.com/nft/", publisher
    )
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx)
    registered_event = erc721_factory.get_event_log(
        ERC721FactoryContract.EVENT_NFT_CREATED,
        tx_receipt.blockNumber,
        web3.eth.block_number,
        None,
    )
    assert registered_event[0].event == "NFTCreated"
    assert registered_event[0].args.admin == publisher.address
    token_address = registered_event[0].args.newTokenAddress
    erc721_token = ERC721Token(web3, token_address)

    """ 
    permissions
    0: manager
    1: deployERC20
    2: updateMetadata
    3: store
    """
    # publisher should be a manager
    assert erc721_token.get_permissions(publisher.address)[0]

    # consumer address should't be manager
    assert not erc721_token.get_permissions(consumer.address)[0]

    erc721_token.add_manager(consumer.address, publisher)

    # consumer now should be manager
    assert erc721_token.get_permissions(consumer.address)[0]

    # check the rest of roles for another_consumer
    assert not erc721_token.get_permissions(another_consumer.address)[0]
    assert not erc721_token.get_permissions(another_consumer.address)[1]
    assert not erc721_token.get_permissions(another_consumer.address)[2]
    assert not erc721_token.get_permissions(another_consumer.address)[3]

    erc721_token.add_to_create_erc20_list(another_consumer.address, consumer)
    erc721_token.addTo725StoreList(another_consumer.address, consumer)
    erc721_token.addToMetadataList(another_consumer.address, consumer)

    # Test rest of add roles functions with newly added manager
    assert erc721_token.get_permissions(another_consumer.address)[1]
    assert erc721_token.get_permissions(another_consumer.address)[2]
    assert erc721_token.get_permissions(another_consumer.address)[3]

    # Remove the manager
    erc721_token.remove_manager(consumer.address, publisher)

    assert not erc721_token.get_permissions(consumer.address)[0]


def test_properties(web3, config):
    """Tests the events' properties."""
    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    assert (
        erc721_factory.event_NFTCreated.abi["name"]
        == ERC721FactoryContract.EVENT_NFT_CREATED
    )
    assert (
        erc721_factory.event_TokenCreated.abi["name"]
        == ERC721FactoryContract.EVENT_TOKEN_CREATED
    )
    assert (
        erc721_factory.event_NewPool.abi["name"] == ERC721FactoryContract.EVENT_NEW_POOL
    )
    assert (
        erc721_factory.event_NewFixedRate.abi["name"]
        == ERC721FactoryContract.EVENT_NEW_FIXED_RATE
    )


def test_fail_create_erc20(web3, config):
    publisher = get_publisher_wallet()

    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))

    with pytest.raises(exceptions.ContractLogicError) as err:
        erc721_factory.create_token(
            1,
            ["ERC20DT1", "ERC20DT1Symbol"],
            [publisher.address, publisher.address, publisher.address, ZERO_ADDRESS],
            [web3.toWei("1.0", "ether"), 0],
            [b""],
            publisher,
        )
    assert (
        err.value.args[0]
        == "execution reverted: VM Exception while processing transaction: revert ERC721Factory: ONLY ERC721 "
        "INSTANCE FROM ERC721FACTORY"
    )


def test_nonexistent_template_index(web3, config):
    publisher = get_publisher_wallet()
    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    with pytest.raises(exceptions.ContractLogicError) as err:
        erc721_factory.deploy_erc721_contract(
            "DT1",
            "DTSYMBOL",
            7,
            ZERO_ADDRESS,
            "https://oceanprotocol.com/nft/",
            publisher,
        )
    assert (
        err.value.args[0]
        == "execution reverted: VM Exception while processing transaction: revert ERC721DTFactory: Template index "
        "doesnt exist"
    )


def test_successful_erc721_creation(web3, config):
    # owner deploys a new ERC721 Contract

    publisher = get_publisher_wallet()

    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    tx = erc721_factory.deploy_erc721_contract(
        "NFT", "NFTSYMBOL", 1, ZERO_ADDRESS, "https://oceanprotocol.com/nft/", publisher
    )
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx)
    registered_event = erc721_factory.get_event_log(
        ERC721FactoryContract.EVENT_NFT_CREATED,
        tx_receipt.blockNumber,
        web3.eth.block_number,
        None,
    )
    assert registered_event[0].event == "NFTCreated"
    assert registered_event[0].args.admin == publisher.address
    token_address = registered_event[0].args.newTokenAddress
    erc721_token = ERC721Token(web3, token_address)
    owner_balance = erc721_token.balance_of(publisher.address)
    assert erc721_token.contract.caller.name() == "NFT"
    assert erc721_token.symbol() == "NFTSYMBOL"
    assert owner_balance == 1


def test_nft_count(web3, config):
    # Tests current NFT count
    publisher = get_publisher_wallet()

    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    current_nft_count = erc721_factory.get_current_nft_count()
    erc721_factory.deploy_erc721_contract(
        "NFT", "NFTSYMBOL", 1, ZERO_ADDRESS, "https://oceanprotocol.com/nft/", publisher
    )
    assert erc721_factory.get_current_nft_count() == current_nft_count + 1


def test_nft_template(web3, config):
    # Tests get NFT template
    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    nft_template = erc721_factory.get_nft_template(1)
    assert nft_template[0] == get_nft_template_address(config)
    assert nft_template[1] is True


def test_erc20_creation(web3, config):
    # owner creates a new ERC20 Contract assigning himself as minter

    publisher = get_publisher_wallet()
    consumer = get_consumer_wallet()
    another_consumer = get_another_consumer_wallet()

    erc721_factory = ERC721FactoryContract(web3, get_nft_factory_address(config))
    tx = erc721_factory.deploy_erc721_contract(
        "NFT", "NFTSYMBOL", 1, ZERO_ADDRESS, "https://oceanprotocol.com/nft/", publisher
    )
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx)
    registered_event = erc721_factory.get_event_log(
        ERC721FactoryContract.EVENT_NFT_CREATED,
        tx_receipt.blockNumber,
        web3.eth.block_number,
        None,
    )
    token_address = registered_event[0].args.newTokenAddress
    erc721_token = ERC721Token(web3, token_address)
    erc721_token.add_to_create_erc20_list(consumer.address, publisher)
    erc_create_data = ErcCreateData(
        1,
        ["ERC20DT1", "ERC20DT1Symbol"],
        [publisher.address, consumer.address, publisher.address, ZERO_ADDRESS],
        [web3.toWei("0.5", "ether"), 0],
        [b""],
    )
    tx_result = erc721_token.create_erc20(erc_create_data, consumer)
    tx_receipt2 = web3.eth.wait_for_transaction_receipt(tx_result)

    registered_event2 = erc721_factory.get_event_log(
        ERC721FactoryContract.EVENT_TOKEN_CREATED,
        tx_receipt2.blockNumber,
        web3.eth.block_number,
        None,
    )

    erc20_address = registered_event2[0].args.newTokenAddress

    erc20_token = ERC20Token(web3, erc20_address)

    permissions = erc20_token.get_permissions(publisher.address)

    assert permissions[0], "Not a minter"
    assert tx_result, "Error creating ERC20 token."

    # Tests failed creation of ERC20
    with pytest.raises(exceptions.ContractLogicError) as err:
        erc721_token.create_erc20(erc_create_data, another_consumer)
    assert (
        err.value.args[0]
        == "execution reverted: VM Exception while processing transaction: revert ERC721Template: NOT "
        "ERC20DEPLOYER_ROLE"
    )


def test_erc20_mint_function(web3, config):
    publisher = get_publisher_wallet()
    consumer = get_consumer_wallet()
    erc721, erc20 = deploy_erc721_erc20(web3, config, publisher, publisher)

    erc20.mint(publisher.address, 10, publisher)
    erc20.mint(consumer.address, 20, publisher)

    assert erc20.balanceOf(publisher.address) == 10
    assert erc20.balanceOf(consumer.address) == 20

    # Tests failed mint
    with pytest.raises(exceptions.ContractLogicError) as err:
        erc20.mint(publisher.address, 10, consumer)
    assert (
        err.value.args[0]
        == "execution reverted: VM Exception while processing transaction: revert ERC20Template: NOT MINTER"
    )

    # Test with another minter
    _, erc20_2 = deploy_erc721_erc20(web3, config, publisher, consumer)

    erc20_2.mint(publisher.address, 10, consumer)
    erc20_2.mint(consumer.address, 20, consumer)

    assert erc20.balanceOf(publisher.address) == 10
    assert erc20.balanceOf(consumer.address) == 20


def test_erc20_set_data(web3, config):
    publisher = get_publisher_wallet()

    erc721, erc20 = deploy_erc721_erc20(web3, config, publisher, publisher)

    """This is a special metadata, it's callable only from the erc20Token contract and
    can be done only by who has deployERC20 rights(rights to create new erc20 token contract)
    the value is stored into the 725Y standard with a predefined key which is the erc20Token address"""

    key = Web3.keccak(hexstr=erc20.address)

    value = Web3.toHex(text="SomeData")

    assert Web3.toHex(erc721.get_data(key)) == "0x"
    erc20.set_data(value, publisher)

    assert Web3.toHex(erc721.get_data(key)) == value
    """This one is the generic version of updating data into the key-value story.
    Only users with 'store' permission can do that.
    NOTE: in this function the key is chosen by the caller."""

    erc721.set_new_data(Web3.keccak(text="arbitrary text"), value, publisher)

    res = erc721.get_data(Web3.keccak(text="arbitrary text"))

    assert Web3.toHex(res) == value


def test_nft_owner_transfer(web3, config):
    publisher = get_publisher_wallet()
    consumer = get_consumer_wallet()

    erc721, erc20 = deploy_erc721_erc20(web3, config, publisher, publisher)

    assert erc721.owner_of(1) == publisher.address

    with pytest.raises(exceptions.ContractLogicError) as err:
        erc721.transfer_from(consumer.address, publisher.address, 1, publisher)
    assert err.value.args[0]
    erc721.transfer_from(publisher.address, consumer.address, 1, publisher)

    assert erc721.balance_of(publisher.address) == 0
    assert erc721.owner_of(1) == consumer.address
    # owner is not NFT owner anymore, nor has any other role, neither older users
    erc_create_data = ErcCreateData(
        1,
        ["ERC20DT1", "ERC20DT1Symbol"],
        [publisher.address, publisher.address, publisher.address, ZERO_ADDRESS],
        [web3.toWei("0.5", "ether"), 0],
        [b""],
    )
    with pytest.raises(exceptions.ContractLogicError) as err:
        erc721.create_erc20(erc_create_data, publisher)
    assert err.value.args[0]
    with pytest.raises(exceptions.ContractLogicError) as err:
        erc20.mint(publisher.address, 10, publisher)
    assert err.value.args[0]

    # newOwner now owns the NFT, is already Manager by default and has all roles
    erc_create_data_new_manager = ErcCreateData(
        1,
        ["ERC20DT1", "ERC20DT1Symbol"],
        [consumer.address, consumer.address, consumer.address, ZERO_ADDRESS],
        [web3.toWei("0.5", "ether"), 0],
        [b""],
    )

    erc721.create_erc20(erc_create_data_new_manager, consumer)
    erc20.add_minter(consumer.address, consumer)

    erc20.mint(consumer.address, 20, consumer)

    assert erc20.balanceOf(consumer.address) == 20
