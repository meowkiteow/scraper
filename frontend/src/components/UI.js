'use client';

export function MetricCard({ label, value, subValue, icon: Icon, color = 'blue' }) {
    const colorMap = {
        blue: 'bg-blue-50 text-blue-600',
        green: 'bg-green-50 text-green-600',
        purple: 'bg-purple-50 text-purple-600',
        orange: 'bg-orange-50 text-orange-600',
        red: 'bg-red-50 text-red-600',
    };

    return (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm font-medium text-gray-500">{label}</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
                    {subValue && <p className="text-xs text-gray-400 mt-1">{subValue}</p>}
                </div>
                {Icon && (
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorMap[color]}`}>
                        <Icon className="w-5 h-5" />
                    </div>
                )}
            </div>
        </div>
    );
}

export function StatusBadge({ status }) {
    const styles = {
        active: 'bg-green-100 text-green-700',
        draft: 'bg-gray-100 text-gray-600',
        paused: 'bg-yellow-100 text-yellow-700',
        completed: 'bg-blue-100 text-blue-700',
        warming: 'bg-orange-100 text-orange-700',
        error: 'bg-red-100 text-red-700',
        replied: 'bg-purple-100 text-purple-700',
        bounced: 'bg-red-100 text-red-700',
        unsubscribed: 'bg-gray-100 text-gray-500',
    };

    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${styles[status] || styles.draft}`}>
            {status}
        </span>
    );
}

export function Button({ children, variant = 'primary', size = 'md', onClick, disabled, className = '', ...props }) {
    const variants = {
        primary: 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm',
        secondary: 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50',
        danger: 'bg-red-600 text-white hover:bg-red-700',
        ghost: 'text-gray-600 hover:bg-gray-100',
        success: 'bg-green-600 text-white hover:bg-green-700',
    };

    const sizes = {
        sm: 'px-3 py-1.5 text-xs',
        md: 'px-4 py-2 text-sm',
        lg: 'px-5 py-2.5 text-base',
    };

    return (
        <button
            onClick={onClick}
            disabled={disabled}
            className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
            {...props}
        >
            {children}
        </button>
    );
}

export function Input({ label, error, className = '', ...props }) {
    return (
        <div className={className}>
            {label && <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>}
            <input
                className={`w-full px-3 py-2 rounded-lg border ${error ? 'border-red-300' : 'border-gray-300'} text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400`}
                {...props}
            />
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        </div>
    );
}

export function Modal({ isOpen, onClose, title, children }) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
            <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto">
                <div className="sticky top-0 bg-white flex items-center justify-between px-6 py-4 border-b border-gray-100 rounded-t-xl">
                    <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
                </div>
                <div className="px-6 py-4">{children}</div>
            </div>
        </div>
    );
}

export function EmptyState({ icon: Icon, title, description, action }) {
    return (
        <div className="text-center py-12">
            {Icon && <Icon className="w-12 h-12 text-gray-300 mx-auto mb-4" />}
            <h3 className="text-sm font-medium text-gray-900">{title}</h3>
            <p className="text-sm text-gray-500 mt-1">{description}</p>
            {action && <div className="mt-4">{action}</div>}
        </div>
    );
}
