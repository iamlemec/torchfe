import time
import torch


class CLogLklhd(torch.autograd.Function):
    maxiter = 10000
    atol = 1e-05

    @staticmethod
    def forward(ctx, beta, y, x, fe, fe_sum, fe_dim, fe_counts):
        resid = y - beta @ x - fe_sum
        for i in range(CLogLklhd.maxiter):
            znorm = 0
            for j in range(fe.shape[0]):
                z = resid.new_zeros(fe_dim[j])
                z.index_add_(0, fe[j], resid)
                z /= fe_counts[j]
                z = z[fe[j]]
                fe_sum += z
                resid -= z
                zn = z.norm(p=float("inf"))
                if zn > znorm:
                    znorm = zn
            if znorm < CLogLklhd.atol:
                print(i)
                break
        grad = -2 * (x @ resid)
        ctx.save_for_backward(grad)
        return torch.sum(torch.pow(resid, 2))

    @staticmethod
    def backward(ctx, grad_output):
        (grad,) = ctx.saved_tensors
        return grad * grad_output, None, None, None, None, None, None


cloglklhd = CLogLklhd.apply


def fit(y, x, fe, maxepochs=100, atol=1e-05, device="cuda"):
    t_secs = time.time()
    y_t = torch.tensor(y, dtype=torch.float32, device=device)
    x_t = torch.tensor(x, dtype=torch.float32, device=device)
    fe_t = torch.tensor(fe, dtype=torch.int64, device=device)
    t_secs_1 = time.time() - t_secs

    fe_dim = fe_t.max(dim=1)[0] + 1
    one_vec = torch.ones_like(y_t)
    fe_counts = [
        torch.zeros(fd, device=device).index_add_(0, fv, one_vec)
        for fd, fv in zip(fe_dim, fe_t)
    ]

    fe_sum = torch.zeros_like(y_t)
    beta = torch.zeros(x_t.shape[0], dtype=torch.float32, device=device)
    beta = beta.requires_grad_(True)

    optimizer = torch.optim.LBFGS([beta])
    prev_loss = torch.mean(torch.pow(y_t - beta @ x_t, 2))

    loss = None
    for __ in range(maxepochs):
        def closure():
            optimizer.zero_grad()
            loss = cloglklhd(beta, y_t, x_t, fe_t, fe_sum, fe_dim, fe_counts)
            loss.backward()
            return loss

        loss = optimizer.step(closure)
        if torch.abs(loss - prev_loss) < atol:
            break
        prev_loss = loss

    t_secs_2 = time.time() - t_secs

    return beta, loss, t_secs_1, t_secs_2
