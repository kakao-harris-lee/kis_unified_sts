import { useEffect } from 'react';

interface ConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  confirmStyle?: 'green' | 'red';
}

function ConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  confirmStyle = 'green',
}: ConfirmationModalProps) {
  // Handle keyboard events
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'Enter') {
        onConfirm();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, onConfirm]);

  if (!isOpen) return null;

  const confirmButtonStyles = {
    green: 'bg-green-600 hover:bg-green-700 text-white',
    red: 'bg-red-600 hover:bg-red-700 text-white',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 rounded-lg p-6 border border-gray-700 max-w-md w-full mx-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-white mb-3">{title}</h3>
        <p className="text-sm text-gray-300 mb-6">{message}</p>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-sm font-medium rounded transition-colors ${confirmButtonStyles[confirmStyle]}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmationModal;
