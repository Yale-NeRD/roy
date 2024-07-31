import React, { useState, useEffect, useRef } from 'react';
import styles from './styles.module.css';

interface SlideInElementProps {
  children: React.ReactNode;
}

const SlideInElement: React.FC<SlideInElementProps> = ({ children }) => {
  const [isVisible, setIsVisible] = useState<boolean>(false);
  const elementRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        } else {
          // Make it invisible if the element is below the viewport
          // i.e., relative Y position is positive
          if (entry.boundingClientRect.top > 0) {
            setIsVisible(false);
          }
        }
      },
      { threshold: [0.5] }
    );

    if (elementRef.current) {
      observer.observe(elementRef.current);
    }

    return () => {
      if (elementRef.current) {
        observer.unobserve(elementRef.current);
      }
    };
  }, []);

  return (
    <section
      ref={elementRef}
      className={`${styles.slide_in_element} ${isVisible ? styles.visible : ''}`}
    >
      {children}
    </section>
  );
};

export default SlideInElement;