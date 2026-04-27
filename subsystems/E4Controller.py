from .py_e4lib import E4Client


class E4Controller:
    def __init__(self):
        self.client = None
        self.connected = False

    async def connect(self, bvp_func, eda_func, acc_func, retries=3, timeout=10):
        for _ in range(retries):
            self.client = await E4Client.find(timeout)
            if self.client is not None:
                break

        if self.client is None:
            return False

        await self.client.__aenter__()
        self.client.enable_bvp(bvp_func)
        self.client.enable_gsr(eda_func)
        self.client.enable_acc(acc_func)

        self.connected = True
        return True

    async def start(self):
        await self.client.start()

    async def end(self):
        if self.client:
            await self.client.stop()
            self.connected = False