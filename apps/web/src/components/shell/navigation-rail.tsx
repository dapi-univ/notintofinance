"use client";

import { BarChart3, Database, PanelLeftClose, PanelLeftOpen, Settings2 } from "lucide-react";

type Props = {
  watchlistCollapsed: boolean;
  onToggleWatchlist: () => void;
};

export function NavigationRail({ watchlistCollapsed, onToggleWatchlist }: Props) {
  const ToggleIcon = watchlistCollapsed ? PanelLeftOpen : PanelLeftClose;
  return (
    <nav className="nav-rail" aria-label="Workspace navigation">
      <div className="nav-rail__mark" aria-label="OLT terminal">
        O
      </div>
      <div className="nav-rail__group">
        <button className="rail-button rail-button--active" type="button" aria-label="Chart workspace" data-tooltip="Chart workspace">
          <BarChart3 aria-hidden="true" size={18} />
        </button>
        <button className="rail-button" type="button" aria-label={watchlistCollapsed ? "Open watchlist" : "Collapse watchlist"} data-tooltip={watchlistCollapsed ? "Open watchlist" : "Collapse watchlist"} onClick={onToggleWatchlist}>
          <ToggleIcon aria-hidden="true" size={18} />
        </button>
        <button className="rail-button" type="button" aria-label="Data status" data-tooltip="Data status">
          <Database aria-hidden="true" size={18} />
        </button>
      </div>
      <button className="rail-button nav-rail__settings" type="button" aria-label="Workspace settings" data-tooltip="Workspace settings">
        <Settings2 aria-hidden="true" size={18} />
      </button>
    </nav>
  );
}
