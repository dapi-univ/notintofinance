"use client";

import { Activity, ChevronDown } from "lucide-react";

import { indicatorDefinitions, type IndicatorId } from "@/lib/indicators/registry";

type Props = {
  enabled: Set<IndicatorId>;
  onToggle: (id: IndicatorId) => void;
};

export function IndicatorMenu({ enabled, onToggle }: Props) {
  return (
    <details className="indicator-menu">
      <summary>
        <Activity aria-hidden="true" size={14} />
        Indicators
        <ChevronDown aria-hidden="true" size={13} />
      </summary>
      <div className="indicator-menu__panel">
        <p className="indicator-menu__title">PANE STUDIES</p>
        {indicatorDefinitions.map((indicator) => {
          const required = indicator.id === "volume";
          return (
            <label key={indicator.id} className="indicator-option">
              <input
                type="checkbox"
                checked={enabled.has(indicator.id)}
                disabled={required}
                onChange={() => onToggle(indicator.id)}
              />
              <span>
                <strong>{indicator.label}</strong>
                <small>{indicator.normalization ?? "Raw shares"}{required ? " · required" : ""}</small>
              </span>
            </label>
          );
        })}
      </div>
    </details>
  );
}
