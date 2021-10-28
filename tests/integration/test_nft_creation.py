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


# TODO owner is already manager and can assign or revoke roles to himself or others


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


def test_erc721_roles(web3, config):
    # NFT Owner is also added as manager when deploying (first time), if transferred that doesn't apply
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
    permissions = erc721_token.get_permissions(publisher.address)
    print("hola")


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
