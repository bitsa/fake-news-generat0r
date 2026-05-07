import { useMemo } from "react";

export interface InlineDiffProps {
  original: string;
  fake: string;
}

interface DiffToken {
  t: "eq" | "del" | "add";
  v: string;
}

function diffTokens(a: string, b: string): DiffToken[] {
  const ax = a.split(/(\s+)/);
  const bx = b.split(/(\s+)/);
  const m = ax.length;
  const n = bx.length;
  const dp: Int32Array[] = Array.from(
    { length: m + 1 },
    () => new Int32Array(n + 1),
  );
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] =
        ax[i] === bx[j]
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffToken[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (ax[i] === bx[j]) {
      out.push({ t: "eq", v: ax[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ t: "del", v: ax[i] });
      i++;
    } else {
      out.push({ t: "add", v: bx[j] });
      j++;
    }
  }
  while (i < m) out.push({ t: "del", v: ax[i++] });
  while (j < n) out.push({ t: "add", v: bx[j++] });
  return out;
}

export function InlineDiff({ original, fake }: InlineDiffProps) {
  const tokens = useMemo(() => diffTokens(original, fake), [original, fake]);
  return (
    <div className="font-serif text-[15px] leading-[1.7] text-text-2">
      {tokens.map((tok, i) => {
        if (tok.t === "eq") return <span key={i}>{tok.v}</span>;
        if (tok.t === "del") {
          return (
            <span
              key={i}
              className="bg-bad/10 text-bad line-through decoration-bad/50"
            >
              {tok.v}
            </span>
          );
        }
        return (
          <span key={i} className="bg-accent/10 text-accent">
            {tok.v}
          </span>
        );
      })}
    </div>
  );
}
