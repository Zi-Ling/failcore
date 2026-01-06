// drift_params_diff.js - highlights drifted fields in parameter display

(function() {
    /**
     * Highlight drifted fields in parameter JSON
     * @param {string} jsonText - JSON string to highlight
     * @param {Array} driftChanges - List of drift changes with field_path
     * @returns {string} - HTML with highlighted fields
     */
    window.highlightDriftFields = function(jsonText, driftChanges) {
        if (!driftChanges || driftChanges.length === 0) {
            return escapeHtml(jsonText);
        }
        
        try {
            // Parse JSON to work with structure
            const obj = JSON.parse(jsonText);
            
            // Build field path map
            const fieldPaths = new Set();
            driftChanges.forEach(change => {
                if (change.field_path) {
                    fieldPaths.add(change.field_path);
                }
            });
            
            // Convert back to JSON with highlighting
            const highlighted = highlightObject(obj, fieldPaths, '');
            
            return highlighted;
        } catch (e) {
            // If JSON parsing fails, return original escaped text
            return escapeHtml(jsonText);
        }
    };
    
    /**
     * Recursively highlight fields in object
     * @param {any} obj - Object/value to highlight
     * @param {Set<string>} fieldPaths - Set of field paths to highlight
     * @param {string} currentPath - Current path prefix
     * @returns {string} - HTML with highlighted fields
     */
    function highlightObject(obj, fieldPaths, currentPath) {
        if (obj === null) {
            return '<span class="json-null">null</span>';
        }
        
        if (typeof obj === 'string') {
            const escaped = escapeHtml(obj);
            const path = currentPath || 'value';
            if (fieldPaths.has(path)) {
                return `<span class="drift-field drift-highlight" data-field="${escapeHtml(path)}">"${escaped}"</span>`;
            }
            return `"${escaped}"`;
        }
        
        if (typeof obj === 'number' || typeof obj === 'boolean') {
            const str = String(obj);
            const path = currentPath || 'value';
            if (fieldPaths.has(path)) {
                return `<span class="drift-field drift-highlight" data-field="${escapeHtml(path)}">${str}</span>`;
            }
            return str;
        }
        
        if (Array.isArray(obj)) {
            if (obj.length === 0) {
                return '[]';
            }
            let result = '[\n';
            obj.forEach((item, index) => {
                const itemPath = currentPath ? `${currentPath}[${index}]` : `[${index}]`;
                const highlighted = highlightObject(item, fieldPaths, itemPath);
                result += '  '.repeat(countPathDepth(currentPath) + 1) + highlighted;
                if (index < obj.length - 1) {
                    result += ',';
                }
                result += '\n';
            });
            result += '  '.repeat(countPathDepth(currentPath)) + ']';
            return result;
        }
        
        if (typeof obj === 'object') {
            const keys = Object.keys(obj);
            if (keys.length === 0) {
                return '{}';
            }
            let result = '{\n';
            keys.forEach((key, index) => {
                const keyPath = currentPath ? `${currentPath}.${key}` : key;
                const escapedKey = escapeHtml(key);
                const value = obj[key];
                const highlightedValue = highlightObject(value, fieldPaths, keyPath);
                
                const indent = '  '.repeat(countPathDepth(currentPath) + 1);
                if (fieldPaths.has(keyPath)) {
                    result += `${indent}<span class="drift-field drift-key" data-field="${escapeHtml(keyPath)}">"${escapedKey}"</span>: ${highlightedValue}`;
                } else {
                    result += `${indent}"${escapedKey}": ${highlightedValue}`;
                }
                if (index < keys.length - 1) {
                    result += ',';
                }
                result += '\n';
            });
            result += '  '.repeat(countPathDepth(currentPath)) + '}';
            return result;
        }
        
        return escapeHtml(String(obj));
    }
    
    function countPathDepth(path) {
        if (!path) return 0;
        return (path.match(/\./g) || []).length;
    }
    
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }
    
    /**
     * Format JSON with drift highlighting (simpler version for code blocks)
     * @param {any} obj - Object to format
     * @param {Array} driftChanges - List of drift changes
     * @returns {string} - Formatted JSON string with class markers
     */
    window.formatJsonWithDrift = function(obj, driftChanges) {
        if (!driftChanges || driftChanges.length === 0) {
            return JSON.stringify(obj, null, 2);
        }
        
        // Build field path map with severity
        const fieldMap = new Map();
        driftChanges.forEach(change => {
            if (change.field_path) {
                fieldMap.set(change.field_path, change.severity || 'info');
            }
        });
        
        // Convert to JSON string first
        const jsonStr = JSON.stringify(obj, null, 2);
        
        // Simple approach: wrap lines containing drifted fields
        // This is a simplified version - full implementation would parse JSON properly
        const lines = jsonStr.split('\n');
        const result = lines.map(line => {
            for (const [fieldPath, severity] of fieldMap.entries()) {
                const fieldName = fieldPath.split('.').pop();
                // Check if line contains the field name
                if (line.includes(`"${fieldName}"`) || line.includes(`'${fieldName}'`)) {
                    return `<span class="drift-field drift-${severity}" data-field="${escapeHtml(fieldPath)}">${escapeHtml(line)}</span>`;
                }
            }
            return escapeHtml(line);
        });
        
        return result.join('\n');
    };
})();
