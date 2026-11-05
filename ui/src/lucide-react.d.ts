declare module 'lucide-react' {
  import type { ComponentType, SVGProps } from 'react'

  type IconProps = SVGProps<SVGSVGElement> & {
    size?: number | string
    strokeWidth?: number | string
  }
  type Icon = ComponentType<IconProps>

  export const Activity: Icon
  export const AlertTriangle: Icon
  export const ArrowLeft: Icon
  export const ArrowDownToLine: Icon
  export const ArrowRight: Icon
  export const ArrowUpRight: Icon
  export const BookOpen: Icon
  export const CalendarClock: Icon
  export const Check: Icon
  export const CheckCircle2: Icon
  export const CircleCheck: Icon
  export const ChevronDown: Icon
  export const ChevronRight: Icon
  export const CircleHelp: Icon
  export const Clock3: Icon
  export const ClipboardCheck: Icon
  export const Database: Icon
  export const Eye: Icon
  export const EyeOff: Icon
  export const FileCheck2: Icon
  export const FileSearch: Icon
  export const FileText: Icon
  export const Fingerprint: Icon
  export const Filter: Icon
  export const GitBranch: Icon
  export const LoaderCircle: Icon
  export const LockKeyhole: Icon
  export const Menu: Icon
  export const Network: Icon
  export const RotateCcw: Icon
  export const Search: Icon
  export const ShieldCheck: Icon
  export const Waypoints: Icon
  export const X: Icon
}
