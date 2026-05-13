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

        # register callbacks
        self.client.on("bvp", bvp_func)
        self.client.on("gsr", eda_func)
        self.client.on("acc", acc_func)

        # connect but DON'T start streaming yet
        await self.client.connect()
        self.connected = True
        return True

    async def start(self):
        await self.client.start()

    async def end(self):
        if self.client:
            await self.client.stop()
            self.connected = False