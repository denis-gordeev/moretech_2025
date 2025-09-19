import React from 'react';
import { HelpCircle } from 'lucide-react';

const MetricTooltip = ({ label, value, description, className = "" }) => {
  const [showTooltip, setShowTooltip] = React.useState(false);

  return (
    <div className={`relative inline-block ${className}`}>
      <div className="flex items-center gap-1">
        <span className="font-medium text-gray-700">{label}:</span>
        <span className="text-gray-600">{value}</span>
        <div 
          className="relative"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <HelpCircle className="w-4 h-4 text-gray-400 hover:text-gray-600 cursor-help" />
          {showTooltip && (
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg shadow-lg z-50 max-w-xs">
              <div className="whitespace-normal">
                {description}
              </div>
              <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MetricTooltip;
