import multiprocessing as mp
import queue
import time
from .engine import estimate
from .schema import ModelConfig
from .serialization import clean


def worker(out,df,config):
    try:
        out.put({'status':'completed','result':clean(estimate(df,ModelConfig(**config)))})
    except BaseException as e:
        out.put({'status':'failed','error':f'{type(e).__name__}: {e}'})


class Job:
    def __init__(self,df,config,dataset_id):
        self.dataset_id=dataset_id
        self.config=config
        self.started=time.monotonic()
        self.state={'status':'running','stage':'校验数据 → 估计模型 → 计算诊断','progress':None}
        ctx=mp.get_context('spawn')
        self.queue=ctx.Queue()
        self.process=ctx.Process(target=worker,args=(self.queue,df,config),daemon=True)
        self.process.start()

    def poll(self):
        if self.state['status']!='running':
            return self.state
        try:
            self.state=self.queue.get_nowait()
            self.process.join(timeout=.1)
            self.queue.close()
        except queue.Empty:
            if time.monotonic()-self.started>180:
                self.cancel('超过 180 秒计算时限。请缩小样本或简化工具变量。','failed')
            elif not self.process.is_alive():
                # Queue feeder may lag process completion very briefly.
                try:
                    self.state=self.queue.get(timeout=.2)
                except queue.Empty:
                    self.state={'status':'failed','error':f'计算进程异常退出（{self.process.exitcode}）。'}
        return self.state

    def cancel(self,reason='任务已取消，未保存估计结果。',state='cancelled'):
        if self.state['status']=='running':
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
                if self.process.is_alive():
                    self.process.kill()
            self.queue.close()
            self.state={'status':state,'error':reason}
