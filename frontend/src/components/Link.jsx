import { Link as RouterLink } from "react-router-dom";

export default function Link({ href, children, className, ...props }) {
  if (typeof href === 'string' && href.startsWith('http')) {
    return <a href={href} className={className} {...props}>{children}</a>;
  }
  return <RouterLink to={href || '#'} className={className} {...props}>{children}</RouterLink>;
}

export const navigate = (to) => {
  window.location.href = to;
};
