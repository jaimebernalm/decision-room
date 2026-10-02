import { translate as tr, useLanguage } from "@/lib/i18n";
import type { ReactNode } from "react";
import { ArrowUpRight, LoaderCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown } from "lucide-react";
import { statuses } from "@/lib/api";
export function Heading({
  title,
  description,
  eyebrow,
  children,
}: {
  title: string;
  description?: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            {eyebrow}
          </p>
        )}
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl break-words">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return children ? (
    <Alert variant={error ? "destructive" : "default"} className="my-3">
      <AlertDescription className="block break-words">
        {typeof children === "string" && error ? tr(children) : children}
      </AlertDescription>
    </Alert>
  ) : null;
}
export function Status({ status }: { status: string }) {
  useLanguage();
  return (
    <Badge
      variant={
        ["failed", "withdrawn"].includes(status) ? "destructive" : "secondary"
      }
      className="whitespace-normal"
    >
      {tr(statuses[status] || status)}
    </Badge>
  );
}
export function Field({
  label,
  children,
  hint,
  id,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  id?: string;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && (
        <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
export function ChoiceSelect({
  label,
  value,
  onChange,
  options,
  id,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  id?: string;
  disabled?: boolean;
}) {
  return (
    <Field label={label} id={id}>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id={id} aria-label={label} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
}
export function Disclosure({
  title,
  children,
  defaultOpen = false,
  subtle = false,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  subtle?: boolean;
}) {
  return (
    <Collapsible
      defaultOpen={defaultOpen}
      className={subtle ? "" : "rounded-lg border p-4"}
    >
      <CollapsibleTrigger
        className={`group flex items-center justify-between gap-3 rounded-sm text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${subtle ? "py-1 text-muted-foreground hover:text-foreground" : "w-full"}`}
      >
        {title}
        <ChevronDown className="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div
          className={`space-y-3 text-sm ${subtle ? "mt-3 rounded-xl border p-4 leading-7" : "pt-4"}`}
        >
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
export function Empty({
  title,
  description,
  href,
  onAction,
  label = tr("Nuevo chat"),
  iconAction,
}: {
  title: string;
  description: string;
  href?: string;
  onAction?: () => void;
  label?: string;
  iconAction?: { label: string; onClick: () => void; disabled?: boolean };
}) {
  useLanguage();
  return (
    <Card className="border-dashed shadow-none">
      <CardContent className="flex min-h-60 flex-col items-center justify-center gap-3 py-12 text-center">
        {iconAction ? (
          <Button
            type="button"
            variant="secondary"
            size="icon"
            className="size-12 rounded-xl"
            aria-label={iconAction.label}
            title={iconAction.label}
            onClick={iconAction.onClick}
            disabled={iconAction.disabled}
          >
            <Plus className="size-5" />
          </Button>
        ) : (
          <div className="rounded-xl bg-muted p-3" aria-hidden="true">
            <Plus className="size-5" />
          </div>
        )}
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="max-w-md text-sm text-muted-foreground">{description}</p>
        {href && (
          <Button asChild className="mt-3">
            <a href={href} onClick={onAction}>
              {label}
              <ArrowUpRight />
            </a>
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
export function Loading() {
  useLanguage();
  return (
    <div role="status" aria-label={tr("Cargando")} className="space-y-5">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
    </div>
  );
}
export function Busy() {
  return (
    <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" />
  );
}
