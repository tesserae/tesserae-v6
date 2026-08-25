import { useCallback, useRef, useState } from 'react';

/**
 * Read one of the assistant's server-sent-event endpoints.
 *
 * The endpoints emit three kinds of event. `facts` carries the computed findings
 * and arrives first, because those are true whether or not the model then
 * succeeds. `chunk` carries generated text a few words at a time. `done` carries
 * the guardrail verdict, which can only be checked once the whole answer exists.
 *
 * Total time to a finished paragraph on the server's CPU is ten to twenty
 * seconds, and the first words arrive in well under one. Streaming is therefore
 * most of the difference between this feeling immediate and feeling broken.
 */
export default function useAssistantStream() {
  const [text, setText] = useState('');
  // What it is doing right now. The searches take a few seconds before any
  // answer text exists, and a blank panel in that gap reads as broken.
  const [step, setStep] = useState(null);
  const [facts, setFacts] = useState(null);
  const [guardrails, setGuardrails] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const stop = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = null;
    setRunning(false);
  }, []);

  const run = useCallback(async (endpoint, body) => {
    stop();
    const controller = new AbortController();
    abortRef.current = controller;
    setText('');
    setStep(null);
    setFacts(null);
    setGuardrails(null);
    setError(null);
    setRunning(true);

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`assistant unavailable (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // SSE frames are separated by a blank line, and a chunk boundary can land
      // mid-frame, so hold the tail until the separator actually arrives.
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() || '';
        for (const frame of frames) {
          const line = frame.split('\n').find((l) => l.startsWith('data:'));
          if (!line) continue;
          let evt;
          try {
            evt = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          if (evt.type === 'chunk') { setText((t) => t + (evt.text || '')); setStep(null); }
          else if (evt.type === 'step') setStep(evt.text || null);
          else if (evt.type === 'facts') setFacts(evt.facts || null);
          else if (evt.type === 'error') setError(evt.error || 'the assistant could not answer');
          else if (evt.type === 'done') setGuardrails(evt.guardrails || { clean: true });
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message);
    } finally {
      setStep(null);
      setRunning(false);
      abortRef.current = null;
    }
  }, [stop]);

  return { text, step, facts, guardrails, running, error, run, stop };
}
