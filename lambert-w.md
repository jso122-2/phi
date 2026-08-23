# lambert-w

#math #hub

The fixed point of f(x) = −eˣ and the Lambert W function.

---

## Connections

→ [[MATH]] ← math hub  
→ [[HOME]] ← grand central  
→ [[attractors]] — this is the fixed point of the neg-exp map  
→ [[mcp-server]] — accessible via `neg_exp_sim`  

---

## The puzzle

`d/dx(−eˣ) = −eˣ` — the function is its own derivative.

This closes the loop analytically, but does it converge numerically?

---

## The fixed point

A fixed point satisfies f(x*) = x*, so:

```
−eˣ* = x*
```

Rearranging:

```
x* · eˣ* = −1          (divide both sides by eˣ* / x*)
(−x*) · e^(−x*) = 1
−x* = W(1)             (principal branch Lambert W)
x* = −W(1)
```

where W is the Lambert W function (inverse of g(w) = w·eʷ).

**Numerically: x* = −W(1) ≈ −0.5671432904097838**

Verify: −e^(−0.5671) ≈ −0.5671 ✓

---

## Stability

The fixed point is stable iff |f′(x*)| < 1:

```
f′(x*) = −eˣ* = x* ≈ −0.5671
|f′(x*)| = e^(x*) = e^(−W(1)) = W(1) ≈ 0.5671 < 1  ✓
```

So the fixed point **is stable** even though d/dx(−eˣ) = −eˣ everywhere —
the key is that at x*, the magnitude of the derivative is W(1) < 1.

---

## Convergence basin

The neg-exp map converges to x* for most starting points.
For large positive x₀, the exponential overflows before reaching x*,
so the simulation clips at ±50. Starting from x₀ < 0 converges quickly.

---

## Run it now

```
/neg-exp 0.0      → converges to x* ≈ −0.5671 in ~20 steps
/neg-exp -0.5     → converges immediately (already near x*)
/neg-exp 5.0      → hits overflow, clips, then converges
```

---

## Auto-linked

→ [[CODE]]
→ [[COMMANDS]]

→ [[cairrn]]
→ [[sims]]
→ [[ana-chi]]

→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[hub-classifier]]
→ [[temporal-index]]
→ [[README]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

→ [[psspps]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[harmonic-index]]
→ [[sessions]]

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[graph]]
→ [[workers]]
→ [[git-log]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

→ [[scratch]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[workers-cairrn-constants]]
→ [[logger]]
→ [[mcp-server-tools-cairrn]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
