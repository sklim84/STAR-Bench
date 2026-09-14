import os, sys, torch, torch.distributed as dist, torch.multiprocessing as mp

def worker(rank, world):
    os.environ["MASTER_ADDR"] = "127.0.0.1"
    os.environ["MASTER_PORT"] = "29517"
    torch.cuda.set_device(rank)
    dist.init_process_group("nccl", rank=rank, world_size=world)
    t = torch.ones(1024, device=f"cuda:{rank}")
    dist.all_reduce(t)
    if rank == 0:
        print("    all_reduce OK, sum =", int(t[0].item()), flush=True)
    dist.destroy_process_group()

if __name__ == "__main__":
    try:
        mp.spawn(worker, args=(2,), nprocs=2, join=True)
        print("    RESULT: PASS", flush=True)
    except Exception as e:
        print("    RESULT: FAIL", type(e).__name__, str(e)[:200], flush=True)
