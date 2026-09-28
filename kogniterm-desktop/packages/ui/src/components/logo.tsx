import { type ComponentProps } from "solid-js"

export const Mark = (props: { class?: string }) => {
  return (
    <svg
      data-component="logo-mark"
      classList={{ [props.class ?? ""]: !!props.class }}
      viewBox="0 0 16 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path data-slot="logo-logo-mark-shadow" d="M12 16H4V8H12V16Z" fill="var(--icon-weak-base)" />
      <path data-slot="logo-logo-mark-o" d="M12 4H4V16H12V4ZM16 20H0V0H16V20Z" fill="var(--icon-strong-base)" />
    </svg>
  )
}

export const Splash = (props: Pick<ComponentProps<"svg">, "ref" | "class">) => {
  return (
    <svg
      ref={props.ref}
      data-component="logo-splash"
      classList={{ [props.class ?? ""]: !!props.class }}
      viewBox="0 0 80 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M60 80H20V40H60V80Z" fill="var(--icon-base)" />
      <path d="M60 20H20V80H60V20ZM80 100H0V0H80V100Z" fill="var(--icon-strong-base)" />
    </svg>
  )
}

export const Logo = (props: { class?: string }) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 252 42"
      fill="none"
      classList={{ [props.class ?? ""]: !!props.class }}
    >
      <g>
        <path d="M6 0H0V36H6V0ZM24 0H12V6H24V0ZM18 6H6V12H18V6ZM12 12H6V24H12V12ZM18 24H6V30H18V24ZM24 30H12V36H24V30Z" fill="var(--icon-base)" />
        <path d="M48 18H36V30H48V18Z" fill="var(--icon-weak-base)" />
        <path d="M54 6H30V12H54V6ZM54 30H30V36H54V30ZM36 12H30V30H36V12ZM54 12H48V30H54V12Z" fill="var(--icon-base)" />
        <path d="M78 18H66V30H78V18Z" fill="var(--icon-weak-base)" />
        <path
          d="M84 6H60V12H84V6ZM84 30H60V36H84V30ZM66 12H60V30H66V12ZM84 12H78V30H84V12ZM84 36H72V42H84V36Z"
          fill="var(--icon-base)"
        />
        <path d="M108 18H96V36H108V18Z" fill="var(--icon-weak-base)" />
        <path d="M96 6H90V36H96V6ZM114 6H90V12H114V6ZM114 12H108V36H114V12Z" fill="var(--icon-base)" />
        <path d="M126 0H120V3H126V0ZM126 6H120V36H126V6Z" fill="var(--icon-base)" />
        <path d="M156 0H132V6H156V0ZM147 6H141V36H147V6Z" fill="var(--icon-strong-base)" />
        <path d="M186 24H168V30H186V24Z" fill="var(--icon-weak-base)" />
        <path
          d="M168 6H162V36H168V6ZM186 6H162V12H186V6ZM186 12H180V18H186V12ZM186 18H168V24H186V18ZM186 30H162V36H186V30Z"
          fill="var(--icon-strong-base)"
        />
        <path d="M198 6H192V36H198V6ZM216 6H192V12H216V6ZM216 12H210V18H216V12Z" fill="var(--icon-strong-base)" />
        <path d="M234 18H228V36H234V18ZM246 18H240V36H246V18Z" fill="var(--icon-weak-base)" />
        <path
          d="M252 6H222V12H252V6ZM228 12H222V36H228V12ZM240 12H234V36H240V12ZM252 12H246V36H252V12Z"
          fill="var(--icon-strong-base)"
        />
      </g>
    </svg>
  )
}
