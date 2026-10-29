/* The monitor connection is owned by offscreen.js. This node always outputs silence. */
class WinstonAudioCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(2048);
    this.offset = 0;
    this.stopped = false;
    this.epoch = 0;
    this.port.onmessage = ({ data }) => {
      if (this.stopped) return;
      if (data?.type === 'stop') {
        this.stopped = true;
        this.offset = 0;
      } else if (data?.type === 'epoch' && Number.isSafeInteger(data.epoch)) {
        this.epoch = data.epoch;
        this.offset = 0;
      } else if (data?.type === 'flush' && data.epoch === this.epoch) {
        if (this.offset) {
          const samples = this.buffer.slice(0, this.offset);
          this.offset = 0;
          this.port.postMessage({ type: 'audio', samples, epoch: this.epoch, flushId: data.id }, [samples.buffer]);
        }
        this.port.postMessage({ type: 'flushed', id: data.id, epoch: this.epoch });
      }
    };
  }

  process(inputs, outputs) {
    for (const output of outputs) {
      for (const channel of output) channel.fill(0);
    }
    if (this.stopped) return false;
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++) {
      let sample = 0;
      for (const channel of channels) sample += channel[i] || 0;
      this.buffer[this.offset++] = sample / channels.length;
      if (this.offset === this.buffer.length) {
        this.port.postMessage({ type: 'audio', samples: this.buffer, epoch: this.epoch }, [this.buffer.buffer]);
        this.buffer = new Float32Array(2048);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor('winston-audio-capture', WinstonAudioCapture);
