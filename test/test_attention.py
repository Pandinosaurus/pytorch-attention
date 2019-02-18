import numpy as np
import pytest

import torch
from attention import attention


def test_apply_mask_3d():
    batch_size, m, n = 3, 4, 5
    sizes = [4, 3, 2]
    values = torch.randn(batch_size, m, n)
    masked = attention.mask3d(values, sizes=sizes).data
    assert values.size() == masked.size() == (batch_size, m, n)
    for i in range(batch_size):
        for j in range(m):
            for k in range(n):
                if j < sizes[i]:
                    assert masked[i,j,k] == values[i,j,k]
                else:
                    assert masked[i,j,k] == 0


@pytest.mark.parametrize('v_mask, v_unmask', [(0, 1), (float('-inf'), 0)])
def test_fill_context_mask(v_mask, v_unmask):
    batch_size, n_q, n_c = 3, 4, 5
    query_sizes = [4, 3, 2]
    context_sizes = [3, 2, 5]
    mask = torch.randn(batch_size, n_q, n_c)
    mask = attention.fill_context_mask(
        mask, sizes=context_sizes,
        v_mask=v_mask, v_unmask=v_unmask)

    for i in range(batch_size):
        for j in range(n_q):
            for k in range(n_c):
                if k < context_sizes[i]:
                    assert mask[i,j,k] == v_unmask
                else:
                    assert mask[i,j,k] == v_mask


def test_dot():
    batch_size, n_q, n_c, d = 31, 18, 15, 22
    q = np.random.normal(0, 1, (batch_size, n_q, d))
    c = np.random.normal(0, 1, (batch_size, n_c, d))

    s = attention.dot(torch.from_numpy(q),
                      torch.from_numpy(c)
                      )
    s = s.data.numpy()

    assert s.shape == (batch_size, n_q, n_c)

    for i in range(batch_size):
        for j in range(n_q):
            for k in range(n_c):
                assert np.allclose(np.dot(q[i,j], c[i,k]), s[i,j,k])


@pytest.mark.parametrize(
    'batch_size,n_q,n_c,d', [
    (1, 1, 6, 11),
    (20, 1, 10, 3),
    (3, 10, 15, 5)])
def test_attention(batch_size, n_q, n_c, d):
    q = np.random.normal(0, 1, (batch_size, n_q, d))
    c = np.random.normal(0, 1, (batch_size, n_c, d))

    w_out, z_out = attention.attend(torch.from_numpy(q),
                                    torch.from_numpy(c),
                                    return_weight=True
                                    )
    w_out = w_out.data.numpy()
    z_out = z_out.data.numpy()

    assert w_out.shape == (batch_size, n_q, n_c)
    assert z_out.shape == (batch_size, n_q, d)

    for i in range(batch_size):
        for j in range(n_q):
            s = [np.dot(q[i,j], c[i,k]) for k in range(n_c)]
            max_s = max(s)
            exp_s = [np.exp(si - max_s) for si in s]
            sum_exp_s = sum(exp_s)

            w_ref = [ei / sum_exp_s for ei in exp_s]
            assert np.allclose(w_ref, w_out[i,j])

            z_ref = sum(w_ref[k] * c[i,k] for k in range(n_c))
            assert np.allclose(z_ref, z_out[i,j])


@pytest.mark.parametrize(
    'batch_size,n_q,n_c,d,p', [
    (1, 1, 6, 11, 5),
    (20, 1, 10, 3, 14),
    (3, 10, 15, 5, 9)])
def test_attention_values(batch_size, n_q, n_c, d, p):
    q = np.random.normal(0, 1, (batch_size, n_q, d))
    c = np.random.normal(0, 1, (batch_size, n_c, d))
    v = np.random.normal(0, 1, (batch_size, n_c, p))

    w_out, z_out = attention.attend(torch.from_numpy(q),
                                    torch.from_numpy(c),
                                    value=torch.from_numpy(v),
                                    return_weight=True
                                    )
    w_out = w_out.data.numpy()
    z_out = z_out.data.numpy()

    assert w_out.shape == (batch_size, n_q, n_c)
    assert z_out.shape == (batch_size, n_q, p)

    for i in range(batch_size):
        for j in range(n_q):
            s = [np.dot(q[i,j], c[i,k]) for k in range(n_c)]
            max_s = max(s)
            exp_s = [np.exp(si - max_s) for si in s]
            sum_exp_s = sum(exp_s)

            w_ref = [ei / sum_exp_s for ei in exp_s]
            assert np.allclose(w_ref, w_out[i,j])

            z_ref = sum(w_ref[k] * v[i,k] for k in range(n_c))
            assert np.allclose(z_ref, z_out[i,j])


@pytest.mark.parametrize(
    'batch_size,n_q,n_c,d,context_sizes', [
    (1, 1, 6, 11, [3]),
    (4, 1, 10, 3, [7, 5, 10, 9])])
def test_attention_masked(batch_size, n_q, n_c, d, context_sizes):
    q = np.random.normal(0, 1, (batch_size, n_q, d))
    c = np.random.normal(0, 1, (batch_size, n_c, d))

    w_out, z_out = attention.attend(torch.from_numpy(q),
                                    torch.from_numpy(c),
                                    context_sizes=context_sizes,
                                    return_weight=True
                                    )
    w_out = w_out.data.numpy()
    z_out = z_out.data.numpy()

    assert w_out.shape == (batch_size, n_q, n_c)
    assert z_out.shape == (batch_size, n_q, d)

    w_checked = np.zeros((batch_size, n_q, n_c), dtype=int)
    z_checked = np.zeros((batch_size, n_q, d), dtype=int)

    for i in range(batch_size):
        for j in range(n_q):
            n = context_sizes[i] if context_sizes is not None else n_c

            s = [np.dot(q[i,j], c[i,k]) for k in range(n)]
            max_s = max(s)
            exp_s = [np.exp(sk - max_s) for sk in s]
            sum_exp_s = sum(exp_s)

            w_ref = [ek / sum_exp_s for ek in exp_s]
            for k in range(n_c):
                if k < n:
                    assert np.allclose(w_ref[k], w_out[i,j,k])
                    w_checked[i,j,k] = 1
                else:
                    assert np.allclose(0, w_out[i,j,k])
                    w_checked[i,j,k] = 1

            z_ref = sum(w_ref[k] * c[i,k] for k in range(n))
            for k in range(d):
                assert np.allclose(z_ref[k], z_out[i,j,k])
                z_checked[i,j,k] = 1

    assert np.all(w_checked == 1)
    assert np.all(z_checked == 1)
