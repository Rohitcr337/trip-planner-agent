import { LoaderCircle } from "lucide-react";

export default function Spinner({ className = "size-4", showText = true }) {
  return (
    <span className="inline-flex items-center gap-2">
      <LoaderCircle aria-hidden="true" className={`${className} animate-spin motion-reduce:animate-none`} />
      {showText && <span aria-hidden="true" className="hidden text-small motion-reduce:inline">In progress</span>}
    </span>
  );
}
