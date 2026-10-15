# Blow-your-mind mode

One moment where the viewer's picture of the subject suddenly gets bigger, the way pi turning up in a
count of block collisions does, or Euler's formula turning out to be a rotation. Use those to calibrate the
*kind* of moment; don't reuse them unless they are the topic.

## What qualifies

- **True, stated precisely.** If it needs conditions, state them. No "this is magic".
- **Earned.** The viewer already holds every piece from earlier in the video; the reveal connects them.
  A surprise that needs new machinery introduced on the spot is just a fact.
- **Native to the topic.** It grows out of what the video built. Never bolt on an unrelated famous result.
- **Explained.** Right after the reveal, show why it isn't a coincidence. The reveal is the question; the
  explanation is the gift, and it is where the rigor goes.

Kinds that work:
- An unexpected constant or structure (pi, e, primes, the golden ratio) where nothing looked circular or exponential.
- Two different things turning out to be one thing (heat flow and random walks; a drum's tones and eigenvalues;
  determinants and area; Fourier coefficients and spinning circles).
- A result that looks impossible but is forced (an answer independent of a parameter; a sum with a surprising
  value; a continuous curve with no tangent anywhere).
- A change of viewpoint that makes something hard trivial (a 3D picture of a 2D problem; complex numbers solving
  a real one; a symmetry).
- The opening hook turning out to be an instance of the general idea all along.
- Outside math, the same shape: a surprising, true connection or consequence (a physical constraint that
  explains a biological form, a scale comparison that resets intuition, an old idea that is secretly a new one).

## Choosing

1. While writing BRIEF.md, list 3 to 5 candidate surprises that genuinely belong to this topic.
2. For each: is it true as stated? Can the video set it up honestly in the time? Will this viewer actually be surprised?
3. Pick the best one. If none passes, don't force it: make the video without it and tell the user in one line
   why nothing fit honestly. A real, modest surprise beats a fake grand one.

## Staging (pattern: `mtk recipe R10`)

1. **Plant**, at least 2 minutes earlier: show the ingredient innocently (a value marked "?", a coincidence the
   narrator notices and leaves alone: "hold on to that").
2. **Build**: the main content quietly assembles the pieces.
3. **Turn**: ask a question whose answer the viewer expects to be mundane.
4. **Reveal**: slow down. The shortest line in the video, with `self.say(..., style="slower, quieter, a little awed")`.
   The picture should land it a beat before the words do (`glow`, `Flash`, a camera pull-back, two objects morphing
   into one). Up to ~2 s of silence is allowed here.
5. **Why**: start the explanation immediately.
6. **Zoom out**: what the connection opens up.

Place it about 65 to 85% of the way through, once the core idea is solid. Not in the first minute; that belongs
to the hook, though the hook may plant it.

## Don't

- Announce it ("get ready to have your mind blown") or use hype words. Let the content carry it.
- Bend the truth for drama, or skip the why.
- Stage more than one. A second one dilutes the first.
