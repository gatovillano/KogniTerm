import { createUniqueId } from "solid-js";

/** Wordmark pixel-block copiado de la v2 (packages/ui/src/v2/components/wordmark-v2.tsx).
 *  Sin fondo: hereda color por CSS (.tui-kogni / .tui-term con fill currentColor). */
export function Wordmark(props: { class?: string }) {
  const mask = createUniqueId();
  const maskGradient = createUniqueId();

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 776.3516 129"
      fill="none"
      class={props.class}
      role="img"
      aria-label="KogniTerm"
    >
      <g opacity="0.6">
        <g mask={`url(#${mask})`}>
          <g opacity="0.16">
            <g class="tui-kogni">
              <path
                opacity="0.7"
                d="M18.4615 0H0V110.143H18.4615V0ZM73.846 0H36.923V18.3572H73.846V0ZM55.3845 18.3572H18.4615V36.7143H55.3845V18.3572ZM36.923 36.7143H18.4615V73.4287H36.923V36.7143ZM55.3845 73.4287H18.4615V91.7858H55.3845V73.4287ZM73.846 91.7858H36.923V110.143H73.846V91.7858Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M166.2748 18H92.4286V36.4286H166.2748V18ZM166.2748 91.7143H92.4286V110.143H166.2748V91.7143ZM110.8901 36.4286H92.4286V91.7143H110.8901V36.4286ZM166.2748 36.4286H147.8133V91.7143H166.2748V36.4286Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M258.7034 18H184.8572V36.4286H258.7034V18ZM258.7034 91.7143H184.8572V110.143H258.7034V91.7143ZM203.3187 36.4286H184.8572V91.7143H203.3187V36.4286ZM258.7034 36.4286H240.2419V91.7143H258.7034V36.4286ZM258.7034 110.143H221.7802V128.571H258.7034V110.143Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M295.7473 18H277.2858V110.143H295.7473V18ZM351.132 18H277.2858V36.4286H351.132V18ZM351.132 36.4286H332.6705V110.143H351.132V36.4286Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M388.1759 0H369.7144V9.2143H388.1759V0ZM388.1759 18H369.7144V110.143H388.1759V18Z"
                fill="currentColor"
              />
            </g>
            <g class="tui-term">
              <path
                opacity="0.7"
                d="M480.6045 0H406.7583V18.4286H480.6045V0ZM452.9121 18.4286H434.4506V110.143H452.9121V18.4286Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M517.6484 18H499.1869V110.143H517.6484V18ZM573.0331 18H499.1869V36.4286H573.0331V18ZM573.0331 36.4286H554.5716V54.8571H573.0331V36.4286ZM573.0331 54.8571H517.6484V73.2857H573.0331V54.8571ZM573.0331 91.7143H499.1869V110.143H573.0331V91.7143Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M610.077 18H591.6155V110.143H610.077V18ZM665.4617 18H591.6155V36.4286H665.4617V18ZM665.4617 36.4286H647.0002V54.8571H665.4617V36.4286Z"
                fill="currentColor"
              />
              <path
                opacity="0.7"
                d="M776.3516 18H684.0441V36.4286H776.3516V18ZM702.5056 36.4286H684.0441V110.143H702.5056V36.4286ZM739.4286 36.4286H720.9671V110.143H739.4286V36.4286ZM776.3516 36.4286H757.8901V110.143H776.3516V36.4286Z"
                fill="currentColor"
              />
            </g>
          </g>
        </g>
      </g>
      <defs>
        <mask
          id={mask}
          style="mask-type:alpha"
          maskUnits="userSpaceOnUse"
          x="0"
          y="0"
          width="776.3516"
          height="129"
        >
          <rect width="776.3516" height="129" fill={`url(#${maskGradient})`} />
        </mask>
        <linearGradient id={maskGradient} x1="388.1758" y1="68" x2="388.1758" y2="129" gradientUnits="userSpaceOnUse">
          <stop stop-color="white" stop-opacity="0.7" />
          <stop offset="1" stop-color="white" stop-opacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}
