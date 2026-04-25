import asyncio
from py_e4lib import E4Client


class E4Controller:
    """
    WIP e4 control script. 
    """

    def __init__(self):
        self.client = E4Client

    async def connect(self, bvp_func, eda_func, acc_func):
        for _ in range(3):
            self.client = await E4Client.find()
            if self.client is not None:
                break

        if self.client is None:
            return False

        async with self.client:
            self.client.enable_bvp(bvp_func)
            self.client.enable_gsr(eda_func)
            self.client.enable_acc(acc_func)

        return True

    async def start(self):
        await self.client.start()

    async def end(self):
        await self.client.stop()
