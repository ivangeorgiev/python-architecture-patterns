import uuid
from domain.model import allocate
import pytest
from flask import url_for

def random_suffix():
    return uuid.uuid4().hex[:6]


def random_sku(name=""):
    return f"sku-{name}-{random_suffix()}"


def random_batchref(name=""):
    return f"batch-{name}-{random_suffix()}"


def random_orderid(name=""):
    return f"order-{name}-{random_suffix()}"



def test_server_is_up_and_running(client):
    res = client.get(url_for('hello_world', _external=True))
    assert res.status_code == 200
    assert b'Hello' in res.data


@pytest.mark.usefixtures("restart_api")
def test_happy_path_returns_201_and_allocated_batch(client, add_stock):
    sku, othersku = random_sku(), random_sku("other")
    earlybatch = random_batchref(1)
    laterbatch = random_batchref(2)
    otherbatch = random_batchref(3)
    add_stock(
        [
            (laterbatch, sku, 100, "2011-01-02"),
            (earlybatch, sku, 100, "2011-01-01"),
            (otherbatch, othersku, 100, None),
        ]
    )
    data = {"orderid": random_orderid(), "sku": sku, "qty": 3}
    url = url_for('allocate_endpoint')

    r = client.post(url, json=data)

    assert r.status_code == 201
    assert r.json["batchref"] == earlybatch


@pytest.mark.usefixtures("restart_api")
def test_allocations_are_persisted(client, add_stock):
    sku = random_sku()
    batch1, batch2 = random_batchref(1), random_batchref(2)
    order1, order2 = random_orderid(1), random_orderid(2)
    add_stock([
        (batch1, sku, 10, '2011-01-01'),
        (batch2, sku, 10, '2011-01-02'),
    ])
    line1 = { 'orderid': order1, 'sku': sku, 'qty': 10 }
    line2 = { 'orderid': order2, 'sku': sku, 'qty': 10 }
    url = url_for('allocate_endpoint')

    # first order uses all stock in batch 1
    r = client.post(url, json=line1)
    assert r.status_code == 201

    # second order should go to batch 2
    r = client.post(url, json=line2)
    assert r.status_code == 201
    assert r.json['batchref'] == batch2

@pytest.mark.skip()
@pytest.mark.usefixtures("restart_api")
def test_400_message_for_out_of_stock(client, add_stock):
    sku, small_batch, large_order = random_sku(), random_batchref(), random_orderid()
    add_stock([
        (small_batch, sku, 10, '2011-01-01'),
    ])
    line = { 'orderid': large_order, 'sku': sku, 'qty': 20 }
    url = url_for('allocate_endpoint')
    r = client.post(url, json=line)
    assert r.status_code == 400
    assert r.json['message'] == f'Cannot allocate sku {sku}. Out of stock.'

@pytest.mark.usefixtures("restart_api")
def test_unhappy_path_returns_400_and_error_message(client):
    unknown_sku, orderid = random_sku(), random_orderid()
    data = {"orderid": orderid, "sku": unknown_sku, "qty": 20}
    url = url_for('allocate_endpoint')
    r = client.post(url, json=data)
    assert r.status_code == 400
    assert r.json["message"] == f"Invalid sku {unknown_sku}."

@pytest.mark.usefixtures("restart_api")
def test_add_batch(client):
    batchref, orderid, sku = random_batchref(), random_orderid(), random_sku()
    data = {
        "ref": batchref, "sku": sku, "qty": 100, "eta": None,
    }
    url = url_for('add_batch')
    r = client.post(url, json=data)
    assert r.status_code == 201

    # Upon successfully aded batch we could allocate
    allocate_url = url_for('allocate_endpoint')
    orderline = {"orderid": orderid, "sku": sku, "qty": 10}
    r = client.post(allocate_url, json=orderline)
    assert r.status_code == 201
    assert r.json["batchref"] == batchref
