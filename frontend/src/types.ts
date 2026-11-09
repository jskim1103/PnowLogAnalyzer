export type Metric = {
  id: string;
  name: string;
  category: string;
  unit: string;
  description: string;
  numerator: string;
  denominator: string;
  formula: string;
  required_data: string[];
  assumptions: string;
};
export type MetricResult = {
  metric_id: string;
  player_id: string;
  variant: string;
  numerator: string;
  denominator: number;
  value: string | null;
  sample_size: number;
  excluded_hands: number;
  confidence_interval: [number, number] | null;
};
export type Player = {
  player_id: string;
  name: string;
  observed_names: string[];
  sessions: number;
  hands: number;
};
export type Session = {
  session_id: string;
  owner: string | null;
  sources: number;
  hands: number;
  reconciled: number;
  start: string | null;
  end: string | null;
};
export type Summary = {
  session_id: string;
  hand_id: string;
  number: number;
  variant: string;
  timestamp: string | null;
  players: string[];
  player_ids: string[];
  pot: string;
  status: string;
  diagnostics: number;
  board: string[];
};
export type HandPage = {
  items: Summary[];
  total: number;
  offset: number;
  limit: number;
};
export type Event = {
  order: number;
  kind: string;
  player_id: { value: string } | null;
  amount: string | null;
  street_total: boolean;
  all_in: boolean;
  cards: { code: string }[];
  street: string | null;
  run: number | null;
  raw: string;
  sources: {
    file_sha256: string;
    record_number: number;
    line_start: number;
    line_end: number;
  }[];
};
export type HandPlayer = {
  player_id: { value: string };
  display_name: string;
  seat: number;
  starting_stack: string;
};
export type FullHand = {
  history: {
    hand_id: string;
    number: number;
    session_id: string;
    variant: string;
    players: HandPlayer[];
    events: Event[];
    button: { value: string } | null;
  };
  boards: { run: number; cards: { code: string }[] }[];
  results: {
    player_id: { value: string };
    net: string | null;
    position: string | null;
    ending_stack: string | null;
    observed_cards: { code: string }[];
  }[];
  decisions: unknown[];
  accounting_reconciled: boolean;
  status: string;
  diagnostics: {
    code: string;
    message: string;
    order: number | null;
    severity: string;
  }[];
};
export type Performance = {
  points: {
    hand_id: string;
    net: string;
    cumulative: string;
    cumulative_bb: string;
    timestamp: string | null;
  }[];
  excluded: number;
  max_drawdown: string;
  bb100: string | null;
};
export type Starting = {
  cells: {
    hand_class: string;
    observations: number;
    voluntary: number;
    raised: number;
    net: string | null;
  }[];
  observed: number;
  eligible_dealt: number;
  features: { feature: string; value: string; observations: number }[];
  note: string;
};
export type ImportResult = {
  session_id: string;
  new_sources: number;
  new_records: number;
  hands: number;
  reconciled: number;
  issues: number;
};
