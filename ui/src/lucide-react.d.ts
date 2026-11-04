declare module 'lucide-react' {
  import type { ComponentType, SVGProps } from 'react'

  type IconProps = SVGProps<SVGSVGElement> & {
    size?: number | string
    strokeWidth?: number | string
  }
  type Icon = ComponentType<IconProps>

  export const Activity: Icon
  export const AlertTriangle: Icon
  export const ArrowDownToLine: Icon
  export const Check: Icon
  export const ChevronDown: Icon
  export const ChevronRight: Icon
  export const CircleHelp: Icon
  export const Clock3: Icon
  export const FileCheck2: Icon
  export const FileSearch: Icon
  export const Filter: Icon
  export const LoaderCircle: Icon
  export const LockKeyhole: Icon
  export const Menu: Icon
  export const RotateCcw: Icon
  export const Search: Icon
  export const ShieldCheck: Icon
  export const X: Icon
}
