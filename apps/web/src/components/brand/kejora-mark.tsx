type Props = {
  className?: string;
  title?: string;
};

export function KejoraMark({ className, title }: Props) {
  const labelled = Boolean(title);
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : true}
      aria-label={title}
    >
      <path d="M18 5.2 20.1 12l6.7 2.2-6.7 2.2L18 23.2l-2.1-6.8-6.7-2.2 6.7-2.2L18 5.2Z" />
      <path d="m7.2 4 .9 2.8 2.7.9-2.7.9-.9 2.8-.9-2.8-2.8-.9 2.8-.9L7.2 4Z" />
      <path d="m25.2 21.2.8 2.5 2.5.8-2.5.8-.8 2.5-.8-2.5-2.5-.8 2.5-.8.8-2.5Z" />
    </svg>
  );
}
