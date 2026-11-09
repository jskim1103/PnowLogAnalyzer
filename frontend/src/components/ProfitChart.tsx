import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import type { Performance } from "../types";
import { number } from "./shared";
export default function ProfitChart({ data }: { data: Performance | null }) {
  return (
    <div className="chart">
      {data?.points.length ? (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart
            data={data.points.map((p, i) => ({
              ...p,
              index: i + 1,
              value: Number(p.cumulative),
            }))}
            margin={{ left: 0, right: 12, top: 12, bottom: 0 }}
          >
            <CartesianGrid stroke="#e7ece7" vertical={false} />
            <XAxis
              dataKey="index"
              tickLine={false}
              axisLine={false}
              minTickGap={35}
              fontSize={11}
            />
            <YAxis tickLine={false} axisLine={false} fontSize={11} width={48} />
            <Tooltip
              formatter={(v) => [number(Number(v)), "Net chips"]}
              labelFormatter={(v) => "Hand " + v}
            />
            <Line
              type="linear"
              dataKey="value"
              stroke="#28775e"
              strokeWidth={2.5}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="subempty">Reconciled results will appear here.</div>
      )}
    </div>
  );
}
