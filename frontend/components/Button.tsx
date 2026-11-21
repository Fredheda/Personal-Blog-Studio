import type { ComponentProps } from "react";

type Props = ComponentProps<"button"> & { variant?: "default" | "primary" };

/** The studio button (spec 7.1, 7.3). The default look comes from the base
 *  rule of app/globals.css; `primary` is the white one: Publish, Create post
 *  and a dialog's default action. */
export function Button({ variant = "default", type = "button", className = "", ...rest }: Props) {
  const look = variant === "primary" ? "border-primary bg-primary font-semibold text-primary-ink" : "";
  return <button type={type} className={`${look} ${className}`.trim()} {...rest} />;
}
