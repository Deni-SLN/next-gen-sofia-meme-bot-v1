import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiError } from "../lib/api";
import { Badge, Card, QueryState, fmtPct, fmtUsd, sumKnown } from "../components/ui";

/** PRD §18.G: loading, empty, stale, error and unavailable must be distinct. */
describe("QueryState - five distinct states", () => {
  it("shows a loading state", () => {
    render(
      <QueryState isLoading isError={false}>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText(/memuat/i)).toBeTruthy();
    expect(screen.queryByText("DATA")).toBeNull();
  });

  it("shows an empty state", () => {
    render(
      <QueryState isLoading={false} isError={false} isEmpty>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText(/belum ada data/i)).toBeTruthy();
    expect(screen.queryByText("DATA")).toBeNull();
  });

  it("shows an error state", () => {
    render(
      <QueryState isLoading={false} isError>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText(/gagal memuat/i)).toBeTruthy();
    expect(screen.queryByText("DATA")).toBeNull();
  });

  it("shows an unavailable state, distinct from an error", () => {
    render(
      <QueryState isLoading={false} isError={false} isUnavailable>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText(/tidak tersedia/i)).toBeTruthy();
    expect(screen.queryByText(/gagal memuat/i)).toBeNull();
    expect(screen.queryByText("DATA")).toBeNull();
  });

  it("shows a stale warning while still rendering the data", () => {
    render(
      <QueryState isLoading={false} isError={false} isStale>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText(/basi/i)).toBeTruthy();
    expect(screen.getByText("DATA")).toBeTruthy();
  });

  it("renders children when the request succeeded and data is fresh", () => {
    render(
      <QueryState isLoading={false} isError={false}>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText("DATA")).toBeTruthy();
    expect(screen.queryByText(/memuat|basi|gagal/i)).toBeNull();
  });

  it("keeps the five states mutually distinct", () => {
    const states = [
      <QueryState isLoading isError={false}>
        <div>D</div>
      </QueryState>,
      <QueryState isLoading={false} isError={false} isEmpty>
        <div>D</div>
      </QueryState>,
      <QueryState isLoading={false} isError>
        <div>D</div>
      </QueryState>,
      <QueryState isLoading={false} isError={false} isUnavailable>
        <div>D</div>
      </QueryState>,
    ];
    const rendered = states.map((s) => render(s).container.textContent);
    expect(new Set(rendered).size).toBe(states.length);
  });
});

describe("QueryState - correlation id", () => {
  it("surfaces the PRD §12.6 request_id on error", () => {
    const err = new ApiError({
      error: {
        code: "PROVIDER_ERROR",
        message: "boom",
        request_id: "abc123",
        status: 503,
      },
    });
    render(
      <QueryState isLoading={false} isError error={err}>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.getByText("abc123")).toBeTruthy();
  });

  it("does not invent a request_id for a non-API error", () => {
    render(
      <QueryState isLoading={false} isError error={new Error("network down")}>
        <div>DATA</div>
      </QueryState>,
    );
    expect(screen.queryByText(/request_id/)).toBeNull();
  });
});

describe("formatters", () => {
  it("renders missing numbers as a dash, never NaN or zero", () => {
    // A missing value must not read as $0.00 - that is "unknown", not "zero".
    for (const v of [null, undefined, Number.NaN]) {
      expect(fmtUsd(v)).toBe("—");
      expect(fmtPct(v)).toBe("—");
    }
  });

  it("renders real zero as zero", () => {
    expect(fmtUsd(0)).toBe("$0.00");
    expect(fmtPct(0)).toBe("+0.00%");
  });

  it("signs percentages", () => {
    expect(fmtPct(1.5)).toBe("+1.50%");
    expect(fmtPct(-2.25)).toBe("-2.25%");
  });
});

/** Regression (Tahap 1): `realized + unrealized` where unrealized is null
 * evaluates to `0 + null === 0`, turning an unvalued position into a measured
 * zero on screen. */
describe("sumKnown", () => {
  it("adds known values", () => {
    expect(sumKnown(1.5, 2.25)).toBe(3.75);
    expect(sumKnown(-5, 5)).toBe(0);
  });

  it("returns null when any part is unknown", () => {
    expect(sumKnown(1.5, null)).toBeNull();
    expect(sumKnown(null, 1.5)).toBeNull();
    expect(sumKnown(0, null)).toBeNull();
    expect(sumKnown(undefined, 1)).toBeNull();
    expect(sumKnown(Number.NaN, 1)).toBeNull();
  });

  it("renders an unknown total as a dash, not as $0.00", () => {
    expect(fmtUsd(sumKnown(0, null))).toBe("—");
    expect(fmtUsd(sumKnown(0, 0))).toBe("$0.00");
  });
});

describe("presentational", () => {
  it("renders a badge with its level", () => {
    render(<Badge level="ok">FRESH</Badge>);
    expect(screen.getByText("FRESH")).toBeTruthy();
  });

  it("renders a card with a title and children", () => {
    render(
      <Card title="Portfolio">
        <div>BODY</div>
      </Card>,
    );
    expect(screen.getByText("Portfolio")).toBeTruthy();
    expect(screen.getByText("BODY")).toBeTruthy();
  });
});