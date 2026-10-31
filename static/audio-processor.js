/**
 * AudioWorkletProcessor for Star Clinic Voice AI Receptionist.
 * Runs on a high-priority real-time audio thread off the main DOM thread.
 * Captures microphone audio, downsamples to 16kHz Float32 PCM,
 * and transfers buffers efficiently via Transferable ArrayBuffers.
 */

class ClinicAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.sourceSampleRate = sampleRate; // In AudioWorkletGlobalScope, sampleRate is the context's rate (e.g. 44100 or 48000)
    this.ratio = this.sourceSampleRate / this.targetSampleRate;
    this.buffer = [];
    this.targetChunkSize = 1024; // Emit in ~64ms frames (1024 samples at 16kHz)
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const inputData = input[0];
    for (let i = 0; i < inputData.length; i++) {
      this.buffer.push(inputData[i]);
    }

    const neededInputSamples = Math.round(this.targetChunkSize * this.ratio);
    while (this.buffer.length >= neededInputSamples) {
      const rawChunk = this.buffer.splice(0, neededInputSamples);
      const resampled = this.resampleTo16k(rawChunk);
      // Transfer the underlying ArrayBuffer without copying
      this.port.postMessage(resampled.buffer, [resampled.buffer]);
    }

    return true;
  }

  resampleTo16k(inputArray) {
    if (this.sourceSampleRate === 16000) {
      return new Float32Array(inputArray);
    }
    const newLength = this.targetChunkSize;
    const result = new Float32Array(newLength);
    const step = (inputArray.length - 1) / (newLength - 1 || 1);

    for (let i = 0; i < newLength; i++) {
      const srcIdx = i * step;
      const idxFloor = Math.floor(srcIdx);
      const idxCeil = Math.min(idxFloor + 1, inputArray.length - 1);
      const interp = srcIdx - idxFloor;
      result[i] = inputArray[idxFloor] * (1 - interp) + inputArray[idxCeil] * interp;
    }
    return result;
  }
}

registerProcessor("clinic-audio-processor", ClinicAudioProcessor);

