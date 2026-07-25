import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { HTMLAttributes } from "svelte/elements";

export type WithElementRef<T> = T & {
  ref?: HTMLElement | null;
};

export type WithoutChild<T> = T & {
  child?: never;
  children?: never;
};

export type WithoutChildrenOrChild<T> = T & {
  children?: never;
  child?: never;
};

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
