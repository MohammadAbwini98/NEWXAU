import {
  Activity,
  BarChart3,
  BrainCircuit,
  CandlestickChart,
  ChartNoAxesCombined,
  CircleGauge,
  Clock3,
  FlaskConical,
  HeartPulse,
  History,
  LayoutDashboard,
  Newspaper,
  Radar,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  type LucideIcon
} from "lucide-react";
import type { ComponentType } from "react";
import { DashboardPage } from "./pages/DashboardPage";
import { ControlUnitPage } from "./pages/ControlUnitPage";
import {
  BacktestingPage,
  IndicatorsPage,
  ModelsPage,
  NewsPage,
  OptimizationPage,
  ReplayPage,
  RiskPage,
  SignalsPage
} from "./pages/DomainPages";
import { ExecutionPage } from "./pages/ExecutionPage";
import { HealthPage } from "./pages/HealthPage";
import { LiveSignalPage } from "./pages/LiveSignalPage";
import { SettingsPage } from "./pages/SettingsPage";

export type RouteId =
  | "dashboard"
  | "live-signal"
  | "execution"
  | "control-unit"
  | "signals"
  | "models"
  | "indicators"
  | "risk"
  | "backtesting"
  | "optimization"
  | "replay"
  | "news"
  | "health"
  | "settings";

export type RouteGroup = "Trading" | "Analysis" | "Research" | "System";

export interface AppRoute {
  id: RouteId;
  label: string;
  description: string;
  group: RouteGroup;
  icon: LucideIcon;
  component: ComponentType;
  readOnly?: boolean;
}

export const routes: AppRoute[] = [
  {
    id: "dashboard",
    label: "Overview",
    description: "Market posture, system readiness, and current opportunity.",
    group: "Trading",
    icon: LayoutDashboard,
    component: DashboardPage
  },
  {
    id: "live-signal",
    label: "Live Signal",
    description: "Current recommendation, price stream, and market context.",
    group: "Trading",
    icon: CandlestickChart,
    component: LiveSignalPage
  },
  {
    id: "execution",
    label: "Execution",
    description: "Broker status, order history, and guarded execution controls.",
    group: "Trading",
    icon: Activity,
    component: ExecutionPage
  },
  {
    id: "control-unit",
    label: "Control Unit",
    description: "Session eligibility, automation gates, and control state.",
    group: "Trading",
    icon: SlidersHorizontal,
    component: ControlUnitPage
  },
  {
    id: "signals",
    label: "Signal History",
    description: "Recommendations, outcomes, and historical evidence.",
    group: "Trading",
    icon: History,
    component: SignalsPage
  },
  {
    id: "models",
    label: "Models",
    description: "Ensemble votes, artifacts, weights, and performance.",
    group: "Analysis",
    icon: BrainCircuit,
    component: ModelsPage
  },
  {
    id: "indicators",
    label: "Indicators",
    description: "Technical features across the active market window.",
    group: "Analysis",
    icon: ChartNoAxesCombined,
    component: IndicatorsPage
  },
  {
    id: "risk",
    label: "Risk",
    description: "Trade eligibility, limits, blocks, and risk quality.",
    group: "Analysis",
    icon: ShieldCheck,
    component: RiskPage
  },
  {
    id: "backtesting",
    label: "Backtesting",
    description: "Historical simulation, walk-forward runs, and evidence.",
    group: "Research",
    icon: BarChart3,
    component: BacktestingPage
  },
  {
    id: "optimization",
    label: "Optimization",
    description: "Threshold candidates and strategy profile evaluation.",
    group: "Research",
    icon: FlaskConical,
    component: OptimizationPage
  },
  {
    id: "replay",
    label: "Replay",
    description: "Inspect the complete decision trail for a signal.",
    group: "Research",
    icon: Radar,
    component: ReplayPage
  },
  {
    id: "news",
    label: "News Intelligence",
    description: "Macro events, market impact, and news risk windows.",
    group: "Research",
    icon: Newspaper,
    component: NewsPage
  },
  {
    id: "health",
    label: "System Health",
    description: "Backend runtime, services, storage, and live connectivity.",
    group: "System",
    icon: HeartPulse,
    component: HealthPage
  },
  {
    id: "settings",
    label: "Settings",
    description: "Desktop appearance, backend lifecycle, and protected credentials.",
    group: "System",
    icon: Settings,
    component: SettingsPage
  }
];

export const routeGroups: RouteGroup[] = ["Trading", "Analysis", "Research", "System"];

export const routeGroupIcons: Record<RouteGroup, LucideIcon> = {
  Trading: Sparkles,
  Analysis: CircleGauge,
  Research: FlaskConical,
  System: Clock3
};
