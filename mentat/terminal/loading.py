from tqdm import tqdm

from mentat.session_stream import StreamMessage


class LoadingHandler:
    def __init__(self):
        self.pbar = None

    def update(self, message: StreamMessage):
        """Create or update a loading bar with text and progress value (0-100)"""
        text = "" if not isinstance(message.data, str) else message.data
        if self.pbar is None:
            self.pbar = tqdm(
                total=100,
                desc=text,
                bar_format="{percentage:3.0f}%|{bar:50}| {desc}",
            )
        elif text:
            self.pbar.set_description(text)

        if message.extra and "progress" in message.extra:
            _progress = min(message.extra["progress"], self.pbar.total - self.pbar.n)
            self.pbar.update(_progress)
            if self.pbar.n == self.pbar.total:
                self.pbar.close()

    def terminate(self):
        if self.pbar is not None:
            self.pbar.close()
            self.pbar = None
