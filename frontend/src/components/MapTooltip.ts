import { TOOLTIP_CONFIG } from "../constants/clearanceThresholds";

export interface TooltipPosition {
  clientX: number;
  clientY: number;
}

const TOOLTIP_CLASS = "map-tooltip";
const VISIBLE_CLASS = "is-visible";

export class MapTooltip {
  private element: HTMLElement;

  constructor(container: HTMLElement = document.body) {
    const existing = container.querySelector<HTMLElement>(`.${TOOLTIP_CLASS}`);
    if (existing) {
      this.element = existing;
    } else {
      this.element = document.createElement("div");
      this.element.className = TOOLTIP_CLASS;
      this.element.setAttribute("role", "tooltip");
      this.element.setAttribute("aria-hidden", "true");
      this.element.style.display = "none";
      this.element.style.visibility = "hidden";
      this.element.style.opacity = "0";
      container.appendChild(this.element);
    }
  }

  public show(content: string, pos: TooltipPosition): void {
    this.element.textContent = content;
    this.element.setAttribute("aria-hidden", "false");
    this.element.style.display = "block";
    this.element.style.visibility = "visible";
    this.element.style.opacity = "1";
    this.element.classList.add(VISIBLE_CLASS);
    this.move(pos);
  }

  public showForElement(content: string, element: Element): void {
    const rect = element.getBoundingClientRect();
    const pos: TooltipPosition = {
      clientX: rect.left + rect.width / 2,
      clientY: rect.top,
    };
    this.show(content, pos);
  }

  public move(pos: TooltipPosition): void {
    const rect = this.element.getBoundingClientRect();
    const tooltipWidth = rect.width || 120;
    const tooltipHeight = rect.height || 40;

    let left = pos.clientX + TOOLTIP_CONFIG.OFFSET_X;
    let top = pos.clientY + TOOLTIP_CONFIG.OFFSET_Y;

    // Viewport overflow protection
    const windowWidth = typeof window !== "undefined" ? window.innerWidth : 800;
    const windowHeight =
      typeof window !== "undefined" ? window.innerHeight : 600;

    if (left + tooltipWidth > windowWidth - TOOLTIP_CONFIG.VIEWPORT_PADDING) {
      left = pos.clientX - tooltipWidth - TOOLTIP_CONFIG.OFFSET_X;
    }
    if (top + tooltipHeight > windowHeight - TOOLTIP_CONFIG.VIEWPORT_PADDING) {
      top = pos.clientY - tooltipHeight - TOOLTIP_CONFIG.OFFSET_Y;
    }

    this.element.style.left = `${Math.max(TOOLTIP_CONFIG.VIEWPORT_PADDING, left)}px`;
    this.element.style.top = `${Math.max(TOOLTIP_CONFIG.VIEWPORT_PADDING, top)}px`;
  }

  public hide(): void {
    this.element.setAttribute("aria-hidden", "true");
    this.element.style.display = "none";
    this.element.style.visibility = "hidden";
    this.element.style.opacity = "0";
    this.element.classList.remove(VISIBLE_CLASS);
  }

  public destroy(): void {
    this.element.remove();
  }
}
