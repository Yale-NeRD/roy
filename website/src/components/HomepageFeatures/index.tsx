import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';
import SlideInElement from '@site/src/components/ScrollPresent';

type FeatureItem = {
  title: string;
  Svg: React.ComponentType<React.ComponentProps<'svg'>>;
  description: JSX.Element;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'Easy to Use',
    Svg: require('@site/static/img/easy_of_use.svg').default,  // undraw_docusaurus_mountain.svg
    description: (
      <>
        Roy makes it easy to create mutable shared objects on Ray. With Roy,
        you do not need to manually create Ray Actors to handle mutability.
      </>
    ),
  },
  {
    title: 'Compatibility with Ray',
    Svg: require('@site/static/img/compat_ray.svg').default,  // undraw_docusaurus_tree
    description: (
      <>
        You can easily mix Roy with Ray
        primitives such as Actors and non-mutable objects.
      </>
    ),
  },
  {
    title: 'Fast',
    Svg: require('@site/static/img/fast.svg').default,  // undraw_docusaurus_react
    description: (
      <>
        Data classes in Roy are written in Cython and running natively on Ray.
        Enjoy any performance and scalability benefits that Ray provides.
      </>
    ),
  },
];

function Feature({title, Svg, description}: FeatureItem) {
  return (
    <SlideInElement>
    <div className={`col col--6 ${styles.centeringColumn}`}>
      <div className={styles.flexContainer}>
          <div className={clsx('row')}>
            <div className={`${styles.flexItem} image-container`}>
              <Svg className={styles.featureSvg} role="img" />
            </div>
            <div className={`${styles.flexItem} ${styles.textContainer}`}>
              <div className="padding-horiz--md">
                <Heading as="h3">{title}</Heading>
                <p>{description}</p>
              </div>
            </div>
          </div>
      </div>
    </div>
    </SlideInElement>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <section className={styles.features}>
      <div className="container">
        {/* <div className="col"> */}
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        {/* </div> */}
      </div>
    </section>
  );
}
