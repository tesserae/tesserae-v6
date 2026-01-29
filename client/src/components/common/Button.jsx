const variants = {
  primary: 'bg-red-700 text-white hover:bg-red-800',
  secondary: 'bg-amber-600 text-white hover:bg-amber-700',
  tertiary: 'bg-rose-100 text-rose-700 border border-rose-300 hover:bg-rose-200',
  neutral: 'bg-gray-100 text-gray-700 border border-gray-300 hover:bg-gray-200',
  danger: 'bg-red-100 text-red-700 border border-red-300 hover:bg-red-200',
  success: 'bg-green-600 text-white hover:bg-green-700'
};

const sizes = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-1.5 text-sm',
  lg: 'px-4 py-2 text-base'
};

const Button = ({ 
  children, 
  variant = 'primary', 
  size = 'md', 
  disabled = false, 
  className = '', 
  ...props 
}) => {
  return (
    <button
      disabled={disabled}
      className={`
        rounded font-medium transition-colors
        ${variants[variant] || variants.primary}
        ${sizes[size] || sizes.md}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;
